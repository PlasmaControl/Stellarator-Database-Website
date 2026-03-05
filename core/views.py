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
from .models import Device, Configuration, Publication, DescRun
from . import schema


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def approved_required(view_func):
    """Decorator: requires login AND admin approval."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_approved:
            return render(request, "core/pending_approval.html")
        return view_func(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_approved:
                error = "Your account is pending admin approval. You will be notified when access is granted."
            else:
                login(request, user)
                next_url = request.GET.get("next", "/")
                return redirect(next_url)
        else:
            error = "Invalid username or password."

    return render(request, "core/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Registration successful! Your account is pending admin approval. "
                "To follow up, email ye2698@princeton.edu.",
            )
            return redirect("login")
    else:
        form = RegistrationForm()

    return render(request, "core/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Main pages
# ---------------------------------------------------------------------------


def home_view(request):
    return render(request, "core/home.html")


def data_description_view(request):
    tables = _get_table_descriptions()
    return render(request, "core/data_description.html", {"tables": tables})


@approved_required
def upload_view(request):
    context = {}
    if request.method == "POST":
        form_type = request.POST.get("form_type", "")

        if form_type == "upload":
            result = _handle_file_upload(request)
            if result["success"]:
                context["upload_success"] = result["message"]
            else:
                context["upload_error"] = result["message"]

        elif form_type == "publication":
            result = _handle_publication_upload(request)
            if result["success"]:
                context["pub_success"] = result["message"]
            else:
                context["pub_error"] = result["message"]

    return render(request, "core/upload.html", context)


def query_view(request):
    return render(request, "core/query.html")


# ---------------------------------------------------------------------------
# AJAX API endpoints
# ---------------------------------------------------------------------------


@require_GET
def api_columns_single(request):
    """Returns filter column options for a selected table (used in the WHERE clause)."""
    table = request.GET.get("tableName", "")
    cols = _OUTPUT_COLUMNS.get(table, {}).get(table)
    if cols is None:
        return HttpResponse("")
    options = '<option value="" selected disabled hidden></option>'
    options += "".join(f'<option value="{c}">{c}</option>' for c in cols)
    return HttpResponse(options)


@require_GET
def api_columns(request):
    """Returns output column options for a selected table (can include related tables)."""
    table = request.GET.get("tableName", "")
    groups = _OUTPUT_COLUMNS.get(table)
    if groups is None:
        return HttpResponse("")
    options = ""
    for group_label, cols in groups.items():
        tbl_name = group_label.replace(" (related)", "")
        for col in cols:
            value = col if "." in col else f"{tbl_name}.{col}"
            label = value.replace(".", "->")
            options += f'<option value="{value}">{label}</option>'
    return HttpResponse(options)


@require_POST
def api_query(request):
    """Executes the database query and returns an HTML table."""
    qtable = request.POST.get("qtable", "").strip()
    qfin = request.POST.get("qfin", "").strip()
    qthr = request.POST.get("qthr", "").strip()
    qfout = request.POST.get("qfout", "").strip()

    if not qtable or not qfout:
        return HttpResponse(
            '<p style="color:red">Please select a table and at least one output column.</p>'
        )

    output_cols = [c.strip() for c in qfout.split(",") if c.strip()]

    # Whitelist validation
    allowed_tables = {
        "desc_runs",
        "configurations",
        "devices",
        "publications",
        "vmec_runs",
    }
    if qtable not in allowed_tables:
        return HttpResponse('<p style="color:red">Invalid table selection.</p>')

    output_groups = _OUTPUT_COLUMNS.get(qtable, {})
    allowed_filter = set(output_groups.get(qtable, []))
    all_output = set()
    groups = output_groups
    for group_label, cols in groups.items():
        tbl_name = group_label.replace(" (related)", "")
        for col in cols:
            all_output.add(col if "." in col else f"{tbl_name}.{col}")

    safe_output = [c for c in output_cols if c in all_output]
    if not safe_output:
        return HttpResponse(
            '<p style="color:red">No valid output columns selected.</p>'
        )

    # Build SQL
    joins = _JOINS.get(qtable, [])
    select_parts = _build_select_parts(qtable, safe_output)
    sql = f"SELECT {', '.join(select_parts)} FROM {qtable}"
    if joins:
        sql += " " + " ".join(joins)

    params = []
    if qfin and qthr and qfin in allowed_filter:
        operator, value = _parse_criteria(qthr)
        if operator:
            # Qualify column with table name to avoid ambiguity
            qualified_col = f"{qtable}.{qfin}"
            if operator.upper() == "LIKE":
                sql += f" WHERE {qualified_col} LIKE ?"
            else:
                sql += f" WHERE {qualified_col} {operator} ?"
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
    html += "<thead><tr>"
    for name in col_names:
        html += f"<th>{name}</th>"
    html += "<th>Details</th>"
    html += "</tr></thead><tbody>"

    for row in rows:
        html += "<tr>"
        for cell in row:
            val = "" if cell is None else str(cell)
            html += f"<td>{val}</td>"
        # Details link placeholder
        html += "<td>—</td>"
        html += "</tr>"

    html += "</tbody></table>"
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


def _safe_cast(val, fn):
    try:
        return fn(val)
    except (TypeError, ValueError):
        return None


_safe_int = lambda v: _safe_cast(v, int)
_safe_float = lambda v: _safe_cast(v, float)


def _safe_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes")


def _parse_csv_first_row(file_obj):
    """Decode and parse a CSV upload; return the first row as a dict."""
    text = file_obj.read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows[0] if rows else None


_CASTERS = {"int": _safe_int, "float": _safe_float, "bool": _safe_bool}


def _fields_from_csv(data, fields, renames=None):
    """Build model kwargs from a CSV row using a schema field list from schema.py.

    Skips fields whose type is None (system-set fields like PKs and FKs).
    Applies renames for columns whose DB name differs from the Django attribute name.
    """
    renames = renames or {}
    result = {}
    for col, dtype, _ in fields:
        if dtype is None:
            continue
        val = data.get(col)
        attr = renames.get(col, col)
        result[attr] = val or "" if dtype == "str" else _CASTERS[dtype](val)
    return result


def _upsert_device(device_file, username):
    """Parse device CSV and create/update the Device record. Returns the Device instance."""
    data = _parse_csv_first_row(device_file)
    if not data:
        return None
    defaults = _fields_from_csv(data, schema.DEVICE_FIELDS, schema.DEVICE_RENAMES)
    defaults.pop("name", None)  # lookup key — handled separately
    defaults["user_created"] = username
    device, _ = Device.objects.get_or_create(
        name=data.get("name", ""), defaults=defaults
    )
    return device


def _upsert_configuration(config_file, username, device_obj=None):
    """Parse configuration CSV and create/update the Configuration record. Returns the Configuration instance."""
    data = _parse_csv_first_row(config_file)
    if not data:
        return None
    defaults = _fields_from_csv(data, schema.CONFIG_FIELDS, schema.CONFIG_RENAMES)
    defaults.pop("name", None)  # lookup key — handled separately
    defaults["user_created"] = username
    if device_obj is not None:
        defaults["device"] = device_obj
    else:
        raw_deviceid = str(data.get("deviceid") or "").strip().lower()
        if raw_deviceid and raw_deviceid not in ("false", "none", "null", "0"):
            found = Device.objects.filter(deviceid=data["deviceid"]).first()
            if found:
                defaults["device"] = found
    config, _ = Configuration.objects.get_or_create(
        name=data.get("name", ""), defaults=defaults
    )
    return config


def _save_desc_run_files(desc_run, zip_file, surface_file, boozer_file, plot3d_file):
    """Save uploaded files to MEDIA_ROOT/<descrunid>/ and update the record."""
    run_dir = os.path.join(settings.MEDIA_ROOT, str(desc_run.descrunid))
    os.makedirs(run_dir, exist_ok=True)
    if zip_file:
        _save_upload(zip_file, run_dir, "equilibrium.zip")
        desc_run.outputfile = f"{desc_run.descrunid}/equilibrium.zip"
    if surface_file:
        _save_upload(surface_file, run_dir, "surface_plot.webp")
        desc_run.surface_plot = f"{desc_run.descrunid}/surface_plot.webp"
    if boozer_file:
        _save_upload(boozer_file, run_dir, "boozer_plot.webp")
        desc_run.boozer_plot = f"{desc_run.descrunid}/boozer_plot.webp"
    if plot3d_file:
        _save_upload(plot3d_file, run_dir, "3d_plot.html")
        desc_run.plot3d = f"{desc_run.descrunid}/3d_plot.html"
    desc_run.save()


def _handle_file_upload(request):
    csv_file = request.FILES.get("descToUpload")
    if not csv_file:
        return {"success": False, "message": "A DESC results CSV file is required."}

    try:
        data = _parse_csv_first_row(csv_file)
        if not data:
            return {"success": False, "message": "The CSV file is empty."}
    except Exception as e:
        return {"success": False, "message": f"Could not parse CSV: {e}"}

    username = request.user.username

    device_obj = None
    try:
        if request.FILES.get("deviceToUpload"):
            device_obj = _upsert_device(request.FILES["deviceToUpload"], username)
    except Exception as e:
        return {"success": False, "message": f"Could not parse device CSV: {e}"}

    config_obj = None
    try:
        if request.FILES.get("configToUpload"):
            config_obj = _upsert_configuration(
                request.FILES["configToUpload"], username, device_obj=device_obj
            )
    except Exception as e:
        return {"success": False, "message": f"Could not parse configuration CSV: {e}"}

    if config_obj is None:
        # CSV column is 'config_name' (W7-X style) or 'configid' (SOLOVEV style)
        config_name = data.get("config_name") or data.get("configid", "")
        if config_name:
            config_obj = Configuration.objects.filter(name=config_name).first()

    desc_fields = _fields_from_csv(data, schema.DESC_RUN_FIELDS)
    desc_fields["user_created"] = username
    desc_fields["config_name"] = config_obj
    desc_fields["date_created"] = date.today()
    desc_run = DescRun.objects.create(**desc_fields)

    _save_desc_run_files(
        desc_run,
        request.FILES.get("zipToUpload"),
        request.FILES.get("surfaceToUpload"),
        request.FILES.get("boozerToUpload"),
        request.FILES.get("plot3dToUpload"),
    )

    return {
        "success": True,
        "message": f"Successfully uploaded DESC run #{desc_run.descrunid}.",
    }


def _handle_publication_upload(request):
    runid = request.POST.get("runid", "").strip()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    doi = request.POST.get("doi", "").strip()
    pub_id = request.POST.get("pub_id", "").strip()
    citation = request.POST.get("citation", "").strip()

    if not pub_id:
        return {"success": False, "message": "Publication ID is required."}

    pub, created = Publication.objects.get_or_create(
        publicationid=pub_id,
        defaults={
            "correspauthor_firstname": first_name,
            "correspauthor_lastname": last_name,
            "DOI": doi,
            "citation": citation,
        },
    )

    if runid:
        try:
            desc_run = DescRun.objects.get(descrunid=int(runid))
            desc_run.publicationid = pub
            desc_run.save(update_fields=["publicationid"])
        except (DescRun.DoesNotExist, ValueError):
            return {"success": False, "message": f"DESC Run ID {runid} not found."}

    action = "Created" if created else "Found existing"
    return {
        "success": True,
        "message": f'{action} publication "{pub_id}" and linked it to DESC Run #{runid or "N/A"}.',
    }


def _save_upload(file_obj, directory, filename):
    path = os.path.join(directory, filename)
    with open(path, "wb") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)


# ---------------------------------------------------------------------------
# Query helpers — column definitions
# ---------------------------------------------------------------------------

# _OUTPUT_COLUMNS[table] maps group labels to column lists.
# The group whose key == table name holds the main (filterable) columns.
# Related groups have keys like 'configurations (related)'.
_OUTPUT_COLUMNS = {
    "desc_runs": {
        "desc_runs": [
            "descrunid",
            "config_name",
            "user_created",
            "description",
            "provenance",
            "version",
            "initialization_method",
            "l_rad",
            "m_pol",
            "n_tor",
            "l_grid",
            "m_grid",
            "n_grid",
            "current_specification",
            "iota_max",
            "iota_min",
            "pressure_max",
            "pressure_min",
            "D_Mercier_min",
            "D_Mercier_max",
            "vacuum",
            "spectral_indexing",
            "sym",
            "publicationid",
            "date_created",
        ],
        "configurations (related)": [
            "configurations.name",
            "configurations.NFP",
            "configurations.class",
            "configurations.stell_sym",
            "configurations.aspect_ratio",
            "configurations.major_radius",
            "configurations.minor_radius",
            "configurations.volume",
            "configurations.volume_averaged_beta",
            "configurations.volume_averaged_B",
            "configurations.total_toroidal_current",
        ],
        "devices (related)": [
            "devices.name",
            "devices.class",
            "devices.NFP",
        ],
        "publications (related)": [
            "publications.publicationid",
            "publications.correspauthor_firstname",
            "publications.correspauthor_lastname",
            "publications.DOI",
            "publications.citation",
        ],
    },
    "configurations": {
        "configurations": [
            "configid",
            "name",
            "deviceid",
            "user_created",
            "NFP",
            "description",
            "provenance",
            "stell_sym",
            "toroidal_flux",
            "aspect_ratio",
            "major_radius",
            "minor_radius",
            "volume",
            "volume_averaged_beta",
            "volume_averaged_B",
            "total_toroidal_current",
            "current_specification",
            "average_elongation",
            "Z_excursion",
            "R_excursion",
            "class",
            "date_created",
        ],
        "devices (related)": [
            "devices.name",
            "devices.class",
            "devices.NFP",
            "devices.stell_sym",
        ],
    },
    "devices": {
        "devices": [
            "deviceid",
            "user_created",
            "name",
            "description",
            "class",
            "NFP",
            "stell_sym",
            "date_created",
            "date_updated",
        ],
        "configurations (related)": [
            "configurations.name",
            "configurations.NFP",
            "configurations.class",
            "configurations.aspect_ratio",
            "configurations.major_radius",
        ],
    },
    "publications": {
        "publications": [
            "publicationid",
            "correspauthor_firstname",
            "correspauthor_lastname",
            "citation",
            "DOI",
        ],
    },
    "vmec_runs": {
        "vmec_runs": [
            "vmecrunid",
            "config_name",
            "user_created",
            "description",
            "provenance",
            "vmec_version",
            "mpol",
            "mtor",
            "publicationid",
            "date_created",
        ],
        "configurations (related)": [
            "configurations.name",
            "configurations.NFP",
            "configurations.class",
            "configurations.stell_sym",
            "configurations.aspect_ratio",
            "configurations.major_radius",
            "configurations.minor_radius",
        ],
        "publications (related)": [
            "publications.publicationid",
            "publications.correspauthor_firstname",
            "publications.correspauthor_lastname",
            "publications.DOI",
            "publications.citation",
        ],
    },
}

_JOINS = {
    "desc_runs": [
        "LEFT JOIN configurations ON desc_runs.config_name = configurations.name",
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
        "LEFT JOIN publications ON desc_runs.publicationid = publications.publicationid",
    ],
    "configurations": [
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
    ],
    "devices": [
        "LEFT JOIN configurations ON devices.deviceid = configurations.deviceid",
    ],
    "publications": [],
    "vmec_runs": [
        "LEFT JOIN configurations ON vmec_runs.config_name = configurations.name",
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
        "LEFT JOIN publications ON vmec_runs.publicationid = publications.publicationid",
    ],
}


def _build_select_parts(table, output_cols):
    """Return SQL SELECT expressions; dotted cols (e.g. 'configurations.NFP') pass through as-is."""
    return [col if "." in col else f"{table}.{col}" for col in output_cols]


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
        return "LIKE", like_match.group(1)

    # >=, <=, !=, >, <, =  followed by optional quotes
    op_match = re.match(r'^(>=|<=|!=|>|<|=)\s*[\'"]?(.+?)[\'"]?\s*$', criteria)
    if op_match:
        return op_match.group(1), op_match.group(2)

    return None, None


# ---------------------------------------------------------------------------
# Data description page data
# ---------------------------------------------------------------------------


def _get_table_descriptions():
    def cols(fields):
        return [(col, desc) for col, _, desc in fields]

    return [
        {
            "id": "desc-runs",
            "title": "desc_runs Table",
            "columns": cols(schema.DESC_RUN_FIELDS),
        },
        {
            "id": "vmec-runs",
            "title": "vmec_runs Table",
            "columns": cols(schema.VMEC_RUN_FIELDS),
        },
        {
            "id": "configurations",
            "title": "configurations Table",
            "columns": cols(schema.CONFIG_FIELDS),
        },
        {
            "id": "devices",
            "title": "devices Table",
            "columns": cols(schema.DEVICE_FIELDS),
        },
        {
            "id": "publications",
            "title": "publications Table",
            "columns": cols(schema.PUBLICATION_FIELDS),
        },
    ]
