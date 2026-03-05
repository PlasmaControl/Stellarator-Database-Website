import os
import re
import csv
import io
from functools import wraps
from datetime import date

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import connection
from django.conf import settings

from .forms import RegistrationForm
from .models import (
    Device, Configuration, Publication, DescRun
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def approved_required(view_func):
    """Decorator: requires login AND admin approval."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_approved:
            return render(request, 'core/pending_approval.html')
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_approved:
                error = 'Your account is pending admin approval. You will be notified when access is granted.'
            else:
                login(request, user)
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
        else:
            error = 'Invalid username or password.'

    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Registration successful! Your account is pending admin approval. '
                'To follow up, email ye2698@princeton.edu.'
            )
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'core/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Main pages
# ---------------------------------------------------------------------------

def home_view(request):
    return render(request, 'core/home.html')


def data_description_view(request):
    tables = _get_table_descriptions()
    return render(request, 'core/data_description.html', {'tables': tables})


@approved_required
def upload_view(request):
    context = {}
    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')

        if form_type == 'upload':
            result = _handle_file_upload(request)
            if result['success']:
                context['upload_success'] = result['message']
            else:
                context['upload_error'] = result['message']

        elif form_type == 'publication':
            result = _handle_publication_upload(request)
            if result['success']:
                context['pub_success'] = result['message']
            else:
                context['pub_error'] = result['message']

    return render(request, 'core/upload.html', context)


def query_view(request):
    return render(request, 'core/query.html')


# ---------------------------------------------------------------------------
# AJAX API endpoints
# ---------------------------------------------------------------------------

@require_GET
def api_columns_single(request):
    """Returns filter column options for a selected table (used in the WHERE clause)."""
    table = request.GET.get('tableName', '')
    cols = _OUTPUT_COLUMNS.get(table, {}).get(table)
    if cols is None:
        return HttpResponse('')
    options = '<option value="" selected disabled hidden></option>'
    options += ''.join(f'<option value="{c}">{c}</option>' for c in cols)
    return HttpResponse(options)


@require_GET
def api_columns(request):
    """Returns output column options for a selected table (can include related tables)."""
    table = request.GET.get('tableName', '')
    groups = _OUTPUT_COLUMNS.get(table)
    if groups is None:
        return HttpResponse('')
    options = ''
    for group_label, cols in groups.items():
        tbl_name = group_label.replace(' (related)', '')
        for col in cols:
            value = col if '.' in col else f'{tbl_name}.{col}'
            label = value.replace('.', '->')
            options += f'<option value="{value}">{label}</option>'
    return HttpResponse(options)


@require_POST
def api_query(request):
    """Executes the database query and returns an HTML table."""
    qtable = request.POST.get('qtable', '').strip()
    qfin = request.POST.get('qfin', '').strip()
    qthr = request.POST.get('qthr', '').strip()
    qfout = request.POST.get('qfout', '').strip()

    if not qtable or not qfout:
        return HttpResponse('<p style="color:red">Please select a table and at least one output column.</p>')

    output_cols = [c.strip() for c in qfout.split(',') if c.strip()]

    # Whitelist validation
    allowed_tables = {'desc_runs', 'configurations', 'devices', 'publications', 'vmec_runs'}
    if qtable not in allowed_tables:
        return HttpResponse('<p style="color:red">Invalid table selection.</p>')

    output_groups = _OUTPUT_COLUMNS.get(qtable, {})
    allowed_filter = set(output_groups.get(qtable, []))
    all_output = set()
    groups = output_groups
    for group_label, cols in groups.items():
        tbl_name = group_label.replace(' (related)', '')
        for col in cols:
            all_output.add(col if '.' in col else f'{tbl_name}.{col}')

    safe_output = [c for c in output_cols if c in all_output]
    if not safe_output:
        return HttpResponse('<p style="color:red">No valid output columns selected.</p>')

    # Build SQL
    joins = _JOINS.get(qtable, [])
    select_parts = _build_select_parts(qtable, safe_output)
    sql = f"SELECT {', '.join(select_parts)} FROM {qtable}"
    if joins:
        sql += ' ' + ' '.join(joins)

    params = []
    if qfin and qthr and qfin in allowed_filter:
        operator, value = _parse_criteria(qthr)
        if operator:
            # Qualify column with table name to avoid ambiguity
            qualified_col = f'{qtable}.{qfin}'
            if operator.upper() == 'LIKE':
                sql += f' WHERE {qualified_col} LIKE ?'
            else:
                sql += f' WHERE {qualified_col} {operator} ?'
            params.append(value)

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        return HttpResponse(f'<p style="color:red">Query error: {e}</p>')

    if not rows:
        return HttpResponse('<p style="color:orange">No results found.</p>')

    # Build HTML table
    html = '<table class="result-table" id="queryResultTable">'
    html += '<thead><tr>'
    for name in col_names:
        html += f'<th>{name}</th>'
    html += '<th>Details</th>'
    html += '</tr></thead><tbody>'

    for row in rows:
        html += '<tr>'
        for cell in row:
            val = '' if cell is None else str(cell)
            html += f'<td>{val}</td>'
        # Details link placeholder
        html += '<td>—</td>'
        html += '</tr>'

    html += '</tbody></table>'
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _parse_csv_first_row(file_obj):
    """Decode and parse a CSV upload; return the first row as a dict."""
    text = file_obj.read().decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows[0] if rows else None


def _upsert_device(device_file, username):
    """Parse device CSV and create/update the Device record."""
    data = _parse_csv_first_row(device_file)
    if data:
        Device.objects.get_or_create(
            name=data.get('name', ''),
            defaults={
                'user_created': username,
                'description': data.get('description', ''),
                'device_class': data.get('class', ''),
                'NFP': _safe_int(data.get('NFP')),
                'stell_sym': _safe_bool(data.get('stell_sym')),
            }
        )


def _upsert_configuration(config_file, username):
    """Parse configuration CSV and create/update the Configuration record."""
    data = _parse_csv_first_row(config_file)
    if data:
        device_obj = None
        if data.get('deviceid'):
            device_obj = Device.objects.filter(deviceid=data['deviceid']).first()
        Configuration.objects.get_or_create(
            name=data.get('name', ''),
            defaults={
                'device': device_obj,
                'user_created': username,
                'NFP': _safe_int(data.get('NFP')),
                'description': data.get('description', ''),
                'provenance': data.get('provenance', ''),
                'config_class': data.get('class', ''),
                'stell_sym': _safe_bool(data.get('stell_sym')),
                'aspect_ratio': _safe_float(data.get('aspect_ratio')),
                'major_radius': _safe_float(data.get('major_radius')),
                'minor_radius': _safe_float(data.get('minor_radius')),
            }
        )


def _save_desc_run_files(desc_run, zip_file, surface_file, boozer_file, plot3d_file):
    """Save uploaded files to MEDIA_ROOT/<descrunid>/ and update the record."""
    run_dir = os.path.join(settings.MEDIA_ROOT, str(desc_run.descrunid))
    os.makedirs(run_dir, exist_ok=True)
    if zip_file:
        _save_upload(zip_file, run_dir, 'equilibrium.zip')
        desc_run.outputfile = f'{desc_run.descrunid}/equilibrium.zip'
    if surface_file:
        _save_upload(surface_file, run_dir, 'surface_plot.webp')
        desc_run.surface_plot = f'{desc_run.descrunid}/surface_plot.webp'
    if boozer_file:
        _save_upload(boozer_file, run_dir, 'boozer_plot.webp')
        desc_run.boozer_plot = f'{desc_run.descrunid}/boozer_plot.webp'
    if plot3d_file:
        _save_upload(plot3d_file, run_dir, '3d_plot.html')
        desc_run.plot3d = f'{desc_run.descrunid}/3d_plot.html'
    desc_run.save()


def _handle_file_upload(request):
    csv_file = request.FILES.get('descToUpload')
    if not csv_file:
        return {'success': False, 'message': 'A DESC results CSV file is required.'}

    try:
        data = _parse_csv_first_row(csv_file)
        if not data:
            return {'success': False, 'message': 'The CSV file is empty.'}
    except Exception as e:
        return {'success': False, 'message': f'Could not parse CSV: {e}'}

    username = request.user.username

    try:
        if request.FILES.get('deviceToUpload'):
            _upsert_device(request.FILES['deviceToUpload'], username)
    except Exception as e:
        return {'success': False, 'message': f'Could not parse device CSV: {e}'}

    try:
        if request.FILES.get('configToUpload'):
            _upsert_configuration(request.FILES['configToUpload'], username)
    except Exception as e:
        return {'success': False, 'message': f'Could not parse configuration CSV: {e}'}

    config_name = data.get('config_name', '')
    config_obj = Configuration.objects.filter(name=config_name).first() if config_name else None

    desc_run = DescRun.objects.create(
        config_name=config_obj,
        user_created=username,
        description=data.get('description', ''),
        provenance=data.get('provenance', ''),
        version=data.get('version', ''),
        initialization_method=data.get('initialization_method', ''),
        l_rad=_safe_int(data.get('l_rad')),
        m_pol=_safe_int(data.get('m_pol')),
        n_tor=_safe_int(data.get('n_tor')),
        l_grid=_safe_int(data.get('l_grid')),
        m_grid=_safe_int(data.get('m_grid')),
        n_grid=_safe_int(data.get('n_grid')),
        inputfilename=data.get('inputfilename', ''),
        outputfile=data.get('outputfile', ''),
        profile_rho=data.get('profile_rho', ''),
        current_specification=data.get('current_specification', ''),
        iota_profile=data.get('iota_profile', ''),
        iota_max=_safe_float(data.get('iota_max')),
        iota_min=_safe_float(data.get('iota_min')),
        current_profile=data.get('current_profile', ''),
        pressure_profile=data.get('pressure_profile', ''),
        pressure_max=_safe_float(data.get('pressure_max')),
        pressure_min=_safe_float(data.get('pressure_min')),
        D_Mercier=data.get('D_Mercier', ''),
        D_Mercier_min=_safe_float(data.get('D_Mercier_min')),
        D_Mercier_max=_safe_float(data.get('D_Mercier_max')),
        vacuum=_safe_bool(data.get('vacuum')),
        spectral_indexing=data.get('spectral_indexing', ''),
        sym=_safe_bool(data.get('sym')),
        date_created=date.today(),
    )

    _save_desc_run_files(
        desc_run,
        request.FILES.get('zipToUpload'),
        request.FILES.get('surfaceToUpload'),
        request.FILES.get('boozerToUpload'),
        request.FILES.get('plot3dToUpload'),
    )

    return {'success': True, 'message': f'Successfully uploaded DESC run #{desc_run.descrunid}.'}


def _handle_publication_upload(request):
    runid = request.POST.get('runid', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    doi = request.POST.get('doi', '').strip()
    pub_id = request.POST.get('pub_id', '').strip()
    citation = request.POST.get('citation', '').strip()

    if not pub_id:
        return {'success': False, 'message': 'Publication ID is required.'}

    pub, created = Publication.objects.get_or_create(
        publicationid=pub_id,
        defaults={
            'correspauthor_firstname': first_name,
            'correspauthor_lastname': last_name,
            'DOI': doi,
            'citation': citation,
        }
    )

    if runid:
        try:
            desc_run = DescRun.objects.get(descrunid=int(runid))
            desc_run.publicationid = pub
            desc_run.save(update_fields=['publicationid'])
        except (DescRun.DoesNotExist, ValueError):
            return {'success': False, 'message': f'DESC Run ID {runid} not found.'}

    action = 'Created' if created else 'Found existing'
    return {
        'success': True,
        'message': f'{action} publication "{pub_id}" and linked it to DESC Run #{runid or "N/A"}.'
    }


def _save_upload(file_obj, directory, filename):
    path = os.path.join(directory, filename)
    with open(path, 'wb') as f:
        for chunk in file_obj.chunks():
            f.write(chunk)


def _safe_cast(val, fn):
    try: return fn(val)
    except (TypeError, ValueError): return None

_safe_int   = lambda v: _safe_cast(v, int)
_safe_float = lambda v: _safe_cast(v, float)


def _safe_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('1', 'true', 'yes')


# ---------------------------------------------------------------------------
# Query helpers — column definitions
# ---------------------------------------------------------------------------

# _OUTPUT_COLUMNS[table] maps group labels to column lists.
# The group whose key == table name holds the main (filterable) columns.
# Related groups have keys like 'configurations (related)'.
_OUTPUT_COLUMNS = {
    'desc_runs': {
        'desc_runs': [
            'descrunid', 'config_name', 'user_created',
            'description', 'provenance', 'version', 'initialization_method',
            'l_rad', 'm_pol', 'n_tor', 'l_grid', 'm_grid', 'n_grid',
            'current_specification', 'iota_max', 'iota_min',
            'pressure_max', 'pressure_min', 'D_Mercier_min', 'D_Mercier_max',
            'vacuum', 'spectral_indexing', 'sym', 'publicationid',
            'date_created',
        ],
        'configurations (related)': [
            'configurations.name', 'configurations.NFP', 'configurations.class',
            'configurations.stell_sym', 'configurations.aspect_ratio',
            'configurations.major_radius', 'configurations.minor_radius',
            'configurations.volume', 'configurations.volume_averaged_beta',
            'configurations.volume_averaged_B', 'configurations.total_toroidal_current',
        ],
        'devices (related)': [
            'devices.name', 'devices.class', 'devices.NFP',
        ],
        'publications (related)': [
            'publications.publicationid', 'publications.correspauthor_firstname',
            'publications.correspauthor_lastname', 'publications.DOI', 'publications.citation',
        ],
    },
    'configurations': {
        'configurations': [
            'configid', 'name', 'deviceid', 'user_created', 'NFP', 'description',
            'provenance', 'stell_sym', 'toroidal_flux', 'aspect_ratio',
            'major_radius', 'minor_radius', 'volume', 'volume_averaged_beta',
            'volume_averaged_B', 'total_toroidal_current', 'current_specification',
            'average_elongation', 'Z_excursion', 'R_excursion', 'class',
            'date_created',
        ],
        'devices (related)': [
            'devices.name', 'devices.class', 'devices.NFP', 'devices.stell_sym',
        ],
    },
    'devices': {
        'devices': [
            'deviceid', 'user_created', 'name', 'description', 'class',
            'NFP', 'stell_sym', 'date_created', 'date_updated',
        ],
        'configurations (related)': [
            'configurations.name', 'configurations.NFP', 'configurations.class',
            'configurations.aspect_ratio', 'configurations.major_radius',
        ],
    },
    'publications': {
        'publications': [
            'publicationid', 'correspauthor_firstname', 'correspauthor_lastname',
            'citation', 'DOI',
        ],
    },
    'vmec_runs': {
        'vmec_runs': [
            'vmecrunid', 'config_name', 'user_created', 'description',
            'provenance', 'vmec_version', 'mpol', 'mtor', 'publicationid',
            'date_created',
        ],
        'configurations (related)': [
            'configurations.name', 'configurations.NFP', 'configurations.class',
            'configurations.stell_sym', 'configurations.aspect_ratio',
            'configurations.major_radius', 'configurations.minor_radius',
        ],
        'publications (related)': [
            'publications.publicationid', 'publications.correspauthor_firstname',
            'publications.correspauthor_lastname', 'publications.DOI', 'publications.citation',
        ],
    },
}

_JOINS = {
    'desc_runs': [
        'LEFT JOIN configurations ON desc_runs.config_name = configurations.name',
        'LEFT JOIN devices ON configurations.deviceid = devices.deviceid',
        'LEFT JOIN publications ON desc_runs.publicationid = publications.publicationid',
    ],
    'configurations': [
        'LEFT JOIN devices ON configurations.deviceid = devices.deviceid',
    ],
    'devices': [
        'LEFT JOIN configurations ON devices.deviceid = configurations.deviceid',
    ],
    'publications': [],
    'vmec_runs': [
        'LEFT JOIN configurations ON vmec_runs.config_name = configurations.name',
        'LEFT JOIN devices ON configurations.deviceid = devices.deviceid',
        'LEFT JOIN publications ON vmec_runs.publicationid = publications.publicationid',
    ],
}


def _build_select_parts(table, output_cols):
    """Return SQL SELECT expressions; dotted cols (e.g. 'configurations.NFP') pass through as-is."""
    return [col if '.' in col else f'{table}.{col}' for col in output_cols]


def _parse_criteria(criteria):
    """
    Parse SQL-style criteria: '>2', '= "SOLOVEV"', 'LIKE "%text%"', etc.
    Returns (operator, value) or (None, None).
    """
    criteria = criteria.strip()
    if not criteria:
        return None, None

    # LIKE 'value' or LIKE "value" or LIKE %value%
    like_match = re.match(r'^LIKE\s+[\'"]?(.+?)[\'"]?\s*$', criteria, re.IGNORECASE)
    if like_match:
        return 'LIKE', like_match.group(1)

    # >=, <=, !=, >, <, =  followed by optional quotes
    op_match = re.match(r'^(>=|<=|!=|>|<|=)\s*[\'"]?(.+?)[\'"]?\s*$', criteria)
    if op_match:
        return op_match.group(1), op_match.group(2)

    return None, None


# ---------------------------------------------------------------------------
# Data description page data
# ---------------------------------------------------------------------------

def _get_table_descriptions():
    return [
        {
            'id': 'desc-runs',
            'title': 'desc_runs Table',
            'columns': [
                ('descrunid', 'Unique identifier for the desc_run'),
                ('config_name', 'Unique identifier for the configuration used to generate this desc_run (further details of the configuration is stored in configurations table)'),
                ('user_created', 'Full name of the user who created this desc_run in the database'),
                ('description', 'Description of the desc_run'),
                ('provenance', 'Short description of where this configuration and desc run came from, e.g. DESC github repo'),
                ('version', 'DESC version used for this simulation'),
                ('initialization_method', 'The method of how the DESC equilibrium solution was initialized — one of "surface", "NAE", "poincare_section", or the name of a .nc or .h5 file corresponding to a VMEC (if .nc) or DESC (if .h5) solution'),
                ('l_rad', 'Radial spectral resolution'),
                ('m_pol', 'Poloidal spectral resolution'),
                ('n_tor', 'Toroidal spectral resolution'),
                ('l_grid', 'Radial grid resolution (usually double the l_rad)'),
                ('m_grid', 'Poloidal grid resolution (usually double the m_pol)'),
                ('n_grid', 'Toroidal grid resolution (usually double the n_tor)'),
                ('inputfilename', 'The name of the input file (if any) used to generate the equilibrium. The ones that have "auto_generated_" prefix are automatically generated by DESC.'),
                ('outputfile', 'The name of the output file as stored in the database.'),
                ('profile_rho', 'rho values used to evaluate iota, current and pressure profiles for the database'),
                ('current_specification', 'If the total enclosed current is given as a profile then this has "net enclosed current" value, if the iota profile is given then "iota"'),
                ('iota_profile', 'Iota profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1'),
                ('iota_max', 'The maximum value of iota calculated on an evenly spaced rho grid of 101 points'),
                ('iota_min', 'The minimum value of iota calculated on an evenly spaced rho grid of 101 points'),
                ('current_profile', 'Current profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1'),
                ('pressure_profile', 'Pressure profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1'),
                ('pressure_max', 'The maximum value of pressure calculated on an evenly spaced rho grid of 101 points'),
                ('pressure_min', 'The minimum value of pressure calculated on an evenly spaced rho grid of 101 points'),
                ('D_Mercier', 'Mercier stability criterion evaluated at 11 evenly spaced radial points from rho=0.1 to rho=1 (positive/negative value denotes stability/instability)'),
                ('D_Mercier_min', 'The minimum value of D_Mercier'),
                ('D_Mercier_max', 'The maximum value of D_Mercier'),
                ('publicationid', 'ID of the publication (as stored in the database) if there is any'),
                ('date_created', 'The date the run was saved to the database (YY/MM/DD)'),
            ],
        },
        {
            'id': 'vmec-runs',
            'title': 'vmec_runs Table',
            'columns': [
                ('vmecrunid', 'Unique identifier for the vmec_run'),
                ('config_name', 'Configuration used for this VMEC run'),
                ('user_created', 'User who created this VMEC run in the database'),
                ('description', 'Description of the VMEC run'),
                ('provenance', 'Short description of where this VMEC run came from'),
                ('vmec_version', 'VMEC version used for this simulation'),
                ('mpol', 'Poloidal mode number'),
                ('mtor', 'Toroidal mode number'),
                ('ns_array', 'Array of radial grid points'),
                ('niter_array', 'Array of maximum iterations'),
                ('ftol_array', 'Array of force tolerance'),
                ('iotaf', 'Iota profile on full grid'),
                ('inputfile', 'Name of the input file'),
                ('outputfile', 'Name of the output file'),
                ('publicationid', 'ID of associated publication if any'),
                ('date_created', 'Date the run was saved to the database'),
            ],
        },
        {
            'id': 'configurations',
            'title': 'configurations Table',
            'columns': [
                ('configid', 'Unique identifier for the configuration'),
                ('name', 'Unique name for the configuration'),
                ('deviceid', 'Unique identifier of the device that this configuration represents, if there is any'),
                ('user_created', 'Full name of the user who created this configuration in database'),
                ('NFP', 'Number of field periods (integer)'),
                ('description', 'Description of this configuration'),
                ('provenance', 'Short description of where this configuration came from, e.g. DESC github repo'),
                ('m', 'Poloidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS'),
                ('n', 'Toroidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS'),
                ('stell_sym', '1 if the configuration is stellarator symmetric, 0 if not'),
                ('toroidal_flux', 'Total toroidal flux Psi'),
                ('aspect_ratio', 'Aspect ratio found by average major radius over average minor radius'),
                ('major_radius', 'Average major radius in meters'),
                ('minor_radius', 'Average minor radius in meters'),
                ('volume', 'Total volume enclosed by the last closed flux surface in cubic meters'),
                ('volume_averaged_beta', 'Volume averaged normalized plasma pressure'),
                ('volume_averaged_B', 'Volume averaged magnetic field in Tesla'),
                ('total_toroidal_current', 'Net toroidal current enclosed by last closed flux surface in Amperes'),
                ('RBC', 'Array of the R_mn cos(mt - nz) coefficients'),
                ('ZBS', 'Array of the Z_mn sin(mt - nz) coefficients'),
                ('RBS', 'Array of the R_mn sin(mt - nz) coefficients'),
                ('ZBC', 'Array of the Z_mn cos(mt - nz) coefficients'),
                ('current_specification', 'The given profile whether iota or net enclosed current'),
                ('pressure_profile_type', 'The type of the given pressure profile, i.e. PowerSeriesProfile, SplineProfile'),
                ('pressure_profile_data1', 'If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).'),
                ('pressure_profile_data2', 'If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.'),
                ('current_profile_type', 'The type of the given current profile (Note: only iota or current profile is given, not both)'),
                ('current_profile_data1', 'If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).'),
                ('current_profile_data2', 'If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.'),
                ('iota_profile_type', 'The type of the given iota profile (Note: only iota or current profile is given, not both)'),
                ('iota_profile_data1', 'If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).'),
                ('iota_profile_data2', 'If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.'),
                ('average_elongation', 'Average elongation, mean(major radius over minor radius)'),
                ('Z_excursion', 'Measure of the excursion in the vertical direction (Z_max - Z_min)'),
                ('R_excursion', 'Measure of the excursion in the radial direction (R_max - R_min)'),
                ('class', 'Class of the configuration: Axisymmetric (AS), Quasi-Axisymmetric (QA), Quasi-Helically Symmetric (QH), etc.'),
                ('date_created', 'The date the configuration was saved to the database (YY/MM/DD)'),
            ],
        },
        {
            'id': 'devices',
            'title': 'devices Table',
            'columns': [
                ('deviceid', 'Unique identifier of the device'),
                ('user_created', 'Full name of the user who created the device in database'),
                ('name', 'Name of the device'),
                ('description', 'Description of the device'),
                ('class', 'Class of the device: Axisymmetric (AS), Quasi-Axisymmetric (QA), Quasi-Helically Symmetric (QH), etc.'),
                ('NFP', 'Number of field periods (integer)'),
                ('stell_sym', '1 if the device is stellarator symmetric, 0 if not'),
                ('date_created', 'The date device is saved to the database (YY/MM/DD)'),
                ('date_updated', 'The date device is updated (YY/MM/DD)'),
            ],
        },
        {
            'id': 'publications',
            'title': 'publications Table',
            'columns': [
                ('publicationid', 'Unique identifier for the publication (string)'),
                ('correspauthor_firstname', 'First name of the corresponding author'),
                ('correspauthor_lastname', 'Last name of the corresponding author'),
                ('citation', 'Citation of the publication'),
                ('DOI', 'Digital Object Identifier (DOI) — a unique key for the publication'),
            ],
        },
    ]
