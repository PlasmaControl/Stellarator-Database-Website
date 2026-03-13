import re
import csv
import io
from functools import wraps
from datetime import date

from django.core.files.storage import default_storage

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import connection
from django.conf import settings

from .forms import RegistrationForm
from .models import Device, Configuration, Publication, DescRun, User
from . import tables as schema


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


def details_view(request, run_type, run_id):
    """Standalone details page for a single DESC or VMEC run (opens in new tab)."""
    from .models import DescRun, VmecRun

    if run_type == "desc":
        run = DescRun.objects.filter(descrunid=run_id).first()
        if run is None:
            return HttpResponse("<h1>Run not found</h1>", status=404)
        pk_col = "descrunid"
        run_label = "DESC"
    elif run_type == "vmec":
        run = VmecRun.objects.filter(vmecrunid=run_id).first()
        if run is None:
            return HttpResponse("<h1>Run not found</h1>", status=404)
        pk_col = "vmecrunid"
        run_label = "VMEC"
    else:
        return HttpResponse("<h1>Unknown run type</h1>", status=404)

    # Collect all raw field values for display (bare column name → value)
    run_data = [(f.column, getattr(run, f.attname)) for f in run._meta.fields]

    config = run.config  # FK object or None
    config_data = (
        [(f.column, getattr(config, f.attname)) for f in config._meta.fields]
        if config
        else []
    )

    pub = run.publication  # FK object or None
    pub_data = (
        [(f.column, getattr(pub, f.attname)) for f in pub._meta.fields] if pub else []
    )

    murl = settings.MEDIA_URL.rstrip("/")

    plot3d_content = ""
    if run_type == "desc" and getattr(run, "plot3d", ""):
        try:
            with default_storage.open(run.plot3d, "rb") as fh:
                plot3d_content = fh.read().decode("utf-8")
        except (OSError, FileNotFoundError):
            plot3d_content = ""

    surface_url = (
        f"{murl}/{run.surface_plot}"
        if run_type == "desc" and getattr(run, "surface_plot", "")
        else None
    )
    boozer_url = (
        f"{murl}/{run.boozer_plot}"
        if run_type == "desc" and getattr(run, "boozer_plot", "")
        else None
    )
    download_url = (
        f"{murl}/{run.outputfile}" if getattr(run, "outputfile", "") else None
    )

    return render(
        request,
        "core/details.html",
        {
            "run_type": run_type,
            "run_label": run_label,
            "run_id": run_id,
            "pk_col": pk_col,
            "run_data": run_data,
            "config": config,
            "config_data": config_data,
            "pub": pub,
            "pub_data": pub_data,
            "plot3d_content": plot3d_content,
            "surface_url": surface_url,
            "boozer_url": boozer_url,
            "download_url": download_url,
        },
    )


@require_POST
def download_all_view(request):
    """Zip all output files for the given DESC run IDs and stream as a single download."""
    import zipfile
    import io
    from .models import DescRun

    runids_str = request.POST.get("descrunids", "")
    runids = [int(x) for x in runids_str.split(",") if x.strip().isdigit()]
    if not runids:
        return HttpResponse("No runs specified.", status=400)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for runid in runids:
            run = DescRun.objects.filter(descrunid=runid).first()
            if run and getattr(run, "outputfile", ""):
                try:
                    with default_storage.open(run.outputfile, "rb") as fh:
                        zf.writestr(f"desc_{runid}_equilibrium.zip", fh.read())
                except (OSError, FileNotFoundError):
                    pass
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="desc_runs.zip"'
    return response


@require_POST
def download_all_vmec_view(request):
    """Zip all output files for the given VMEC run IDs and stream as a single download."""
    import zipfile
    import io
    from .models import VmecRun

    runids_str = request.POST.get("vmecrunids", "")
    runids = [int(x) for x in runids_str.split(",") if x.strip().isdigit()]
    if not runids:
        return HttpResponse("No runs specified.", status=400)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for runid in runids:
            run = VmecRun.objects.filter(vmecrunid=runid).first()
            if run and getattr(run, "outputfile", ""):
                try:
                    with default_storage.open(run.outputfile, "rb") as fh:
                        zf.writestr(f"vmec_{runid}_output.zip", fh.read())
                except (OSError, FileNotFoundError):
                    pass
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="vmec_runs.zip"'
    return response


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

        elif form_type == "device":
            result = _handle_device_upload(request)
            if result["success"]:
                context["device_success"] = result["message"]
            else:
                context["device_error"] = result["message"]

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
        tbl_name = group_label
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
        tbl_name = group_label
        for col in cols:
            all_output.add(col if "." in col else f"{tbl_name}.{col}")

    safe_output = [c for c in output_cols if c in all_output]
    if not safe_output:
        return HttpResponse(
            '<p style="color:red">No valid output columns selected.</p>'
        )

    # If the user applied a filter, ensure that column appears in the output
    # even if they didn't select it explicitly.
    if qfin and qfin in allowed_filter:
        qualified_filter = f"{qtable}.{qfin}"
        if qualified_filter not in safe_output:
            safe_output.insert(0, qualified_filter)

    # Always show the primary key of the queried table as the first visible column.
    _TABLE_PK = {
        "desc_runs": "descrunid",
        "configurations": "configid",
        "devices": "deviceid",
        "publications": "publicationid",
        "vmec_runs": "vmecrunid",
    }
    pk_col = _TABLE_PK.get(qtable)
    if pk_col:
        qualified_pk = f"{qtable}.{pk_col}"
        if qualified_pk in safe_output:
            safe_output.remove(qualified_pk)
        safe_output.insert(0, qualified_pk)

    # Detect whether desc_runs / vmec_runs data is in the result
    # (either as the primary table or via related columns selected by the user).
    has_desc = qtable == "desc_runs" or any(
        c.startswith("desc_runs.") for c in safe_output
    )
    has_vmec = qtable == "vmec_runs" or any(
        c.startswith("vmec_runs.") for c in safe_output
    )

    # Extra columns needed for link/media generation — added to SELECT but hidden in display.
    extra_qualified = []
    hidden_cols = set()

    if has_desc:
        for c in ["descrunid", "surface_plot", "boozer_plot"]:
            if f"desc_runs.{c}" not in safe_output:
                extra_qualified.append(f"desc_runs.{c}")
                hidden_cols.add(c)
        # Alias outputfile to avoid collision with vmec_runs.outputfile
        if "desc_runs.outputfile" not in safe_output:
            extra_qualified.append("desc_runs.outputfile AS desc_outputfile")
            hidden_cols.add("desc_outputfile")

    if has_vmec:
        if "vmec_runs.vmecrunid" not in safe_output:
            extra_qualified.append("vmec_runs.vmecrunid")
            hidden_cols.add("vmecrunid")
        if "vmec_runs.outputfile" not in safe_output:
            extra_qualified.append("vmec_runs.outputfile AS vmec_outputfile")
            hidden_cols.add("vmec_outputfile")

    # Build SQL
    joins = _JOINS.get(qtable, [])
    all_select = safe_output + extra_qualified
    select_parts = _build_select_parts(qtable, all_select)
    sql = f"SELECT {', '.join(select_parts)} FROM {qtable}"
    if joins:
        sql += " " + " ".join(joins)

    params = []
    if qfin and qthr and qfin in allowed_filter:
        operator, value = _parse_criteria(qthr)
        if operator:
            qualified_col = f"{qtable}.{qfin}"
            if operator.upper() == "LIKE":
                sql += f" WHERE {qualified_col} LIKE %s"
            else:
                sql += f" WHERE {qualified_col} {operator} %s"
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

    # Build username → full name map for display
    _fullname = {
        u.username: u.get_full_name() or u.username
        for u in User.objects.only("username", "first_name", "last_name")
    }

    murl = settings.MEDIA_URL.rstrip("/")
    dl_runids = []  # descrunids with output files
    dl_vmec_runids = []  # vmecrunids with output files

    # Build HTML table header — Details first, data columns, then media columns at end
    html = '<table class="result-table" id="queryResultTable">'
    html += "<thead><tr>"
    if has_desc:
        html += "<th>DESC Details</th>"
    if has_vmec:
        html += "<th>VMEC Details</th>"
    for name in col_names:
        if name not in hidden_cols:
            html += f"<th>{name}</th>"
    if has_desc:
        html += "<th>Surface Plot</th><th>Boozer Plot</th><th>Download</th>"
    html += "</tr></thead><tbody>"

    for row in rows:
        row_dict = dict(zip(col_names, row))
        html += "<tr>"

        # Details links — first columns
        if has_desc:
            desc_id = row_dict.get("descrunid")
            if desc_id is not None:
                detail_link = (
                    f"<a href='/details/desc/{desc_id}/' target='_blank'>Click</a>"
                )
            else:
                detail_link = "No Data"
            html += f"<td>{detail_link}</td>"

        if has_vmec:
            vmec_id = row_dict.get("vmecrunid")
            if vmec_id is not None:
                detail_link = (
                    f"<a href='/details/vmec/{vmec_id}/' target='_blank'>Click</a>"
                )
            else:
                detail_link = "No Data"
            html += f"<td>{detail_link}</td>"

        # Regular display columns (skip hidden media columns)
        for name, cell in zip(col_names, row):
            if name in hidden_cols:
                continue
            if name == "user_created" and cell:
                val = _fullname.get(str(cell), str(cell))
            else:
                val = "" if cell is None else str(cell)
            html += f"<td>{val}</td>"

        # Surface Plot / Boozer Plot / Download — whenever desc_runs are in the result
        if has_desc:
            surf = row_dict.get("surface_plot") or ""
            booz = row_dict.get("boozer_plot") or ""
            outf = row_dict.get("desc_outputfile") or ""
            surf_cell = (
                f"<span class='img-popup' data-src='{murl}/{surf}' style='cursor:pointer;'>Image</span>"
                if surf
                else "Missing Image"
            )
            booz_cell = (
                f"<span class='img-popup' data-src='{murl}/{booz}' style='cursor:pointer;'>Image</span>"
                if booz
                else "Missing Image"
            )
            dl_cell = f"<a href='{murl}/{outf}' name='download-button-each'>DESC</a>" if outf else "Missing File"
            html += f"<td>{surf_cell}</td><td>{booz_cell}</td><td>{dl_cell}</td>"
            if outf and row_dict.get("descrunid") is not None:
                dl_runids.append(str(row_dict["descrunid"]))

        if has_vmec:
            vmec_outf = row_dict.get("vmec_outputfile") or ""
            if vmec_outf and row_dict.get("vmecrunid") is not None:
                dl_vmec_runids.append(str(row_dict["vmecrunid"]))

        html += "</tr>"

    html += "</tbody></table>"
    if dl_runids:
        ids = ",".join(dl_runids)
        html += (
            f'<div id="dl-all-meta" data-runids="{ids}" style="display:none;"></div>'
        )
    if dl_vmec_runids:
        ids = ",".join(dl_vmec_runids)
        html += (
            f'<div id="dl-vmec-meta" data-runids="{ids}" style="display:none;"></div>'
        )
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


def _fields_from_csv(data, fields):
    """Build model kwargs from a CSV row using a schema field list.

    Skips fields whose type is None (system-set fields like PKs and FKs).
    Column names in the schema are the same as Django attribute names.
    """
    result = {}
    for col, dtype, _ in fields:
        if dtype is None:
            continue
        val = data.get(col)
        result[col] = val or "" if dtype in ("str", "text") else _CASTERS[dtype](val)
    return result


def _create_device(device_file, username):
    """Parse device CSV and always create a new Device record. Returns the Device instance."""
    data = _parse_csv_first_row(device_file)
    if not data:
        return None
    defaults = _fields_from_csv(data, schema.DEVICE_FIELDS)
    defaults.pop("name", None)
    defaults["user_created"] = username
    return Device.objects.create(name=data.get("name", ""), **defaults)


def _create_configuration(config_file, username, device_obj=None):
    """Parse configuration CSV and always create a new Configuration record. Returns the Configuration instance."""
    data = _parse_csv_first_row(config_file)
    if not data:
        return None
    defaults = _fields_from_csv(data, schema.CONFIG_FIELDS)
    defaults.pop("name", None)
    defaults["user_created"] = username
    if device_obj is not None:
        defaults["device"] = device_obj
    else:
        raw_deviceid = str(data.get("deviceid") or "").strip().lower()
        if raw_deviceid and raw_deviceid not in ("false", "none", "null", "0"):
            found = Device.objects.filter(deviceid=data["deviceid"]).first()
            if found:
                defaults["device"] = found
    return Configuration.objects.create(name=data.get("name", ""), **defaults)


def _save_desc_run_files(desc_run, zip_file, surface_file, boozer_file, plot3d_file):
    """Save uploaded files via default_storage (local or S3) and update the record."""
    rid = desc_run.descrunid
    folder = f"descruns/desc-id-{rid}"
    if zip_file:
        desc_run.outputfile = default_storage.save(
            f"{folder}/desc-eq-id{rid}.zip", zip_file
        )
    if surface_file:
        desc_run.surface_plot = default_storage.save(
            f"{folder}/desc-surface-id{rid}.webp", surface_file
        )
    if boozer_file:
        desc_run.boozer_plot = default_storage.save(
            f"{folder}/desc-boozer-id{rid}.webp", boozer_file
        )
    if plot3d_file:
        desc_run.plot3d = default_storage.save(
            f"{folder}/desc-3dplot-id{rid}.html", plot3d_file
        )
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
            device_obj = _create_device(request.FILES["deviceToUpload"], username)
    except Exception as e:
        return {"success": False, "message": f"Could not parse device CSV: {e}"}

    config_obj = None
    try:
        if request.FILES.get("configToUpload"):
            config_obj = _create_configuration(
                request.FILES["configToUpload"], username, device_obj=device_obj
            )
    except Exception as e:
        return {"success": False, "message": f"Could not parse configuration CSV: {e}"}

    if config_obj is None:
        # No config file uploaded — link to existing config by its integer PK
        raw = str(data.get("configid", "")).strip()
        if raw.isdigit():
            config_obj = Configuration.objects.filter(configid=int(raw)).first()

    desc_fields = _fields_from_csv(data, schema.DESC_RUN_FIELDS)
    desc_fields["user_created"] = username
    desc_fields["config"] = config_obj
    desc_fields["date_created"] = date.today()
    desc_run = DescRun.objects.create(**desc_fields)

    _save_desc_run_files(
        desc_run,
        request.FILES.get("zipToUpload"),
        request.FILES.get("surfaceToUpload"),
        request.FILES.get("boozerToUpload"),
        request.FILES.get("plot3dToUpload"),
    )

    parts = [f"DESC run #{desc_run.descrunid}"]
    if config_obj:
        parts.append(f"configuration #{config_obj.configid}")
    if device_obj:
        parts.append(f"device #{device_obj.deviceid}")
    return {
        "success": True,
        "message": f"Successfully uploaded: {', '.join(parts)}.",
    }


def _handle_device_upload(request):
    name = request.POST.get("device_name", "").strip()
    description = request.POST.get("device_description", "").strip()
    configid_raw = request.POST.get("device_configid", "").strip()

    if not name:
        return {"success": False, "message": "Device name is required."}

    device = Device.objects.create(
        name=name,
        description=description,
        user_created=request.user.username,
        date_created=date.today(),
    )

    linked_config = None
    if configid_raw.isdigit():
        config = Configuration.objects.filter(configid=int(configid_raw)).first()
        if config is None:
            return {
                "success": True,
                "message": (
                    f"Created device #{device.deviceid} ({name}) but "
                    f"configuration #{configid_raw} was not found — not linked."
                ),
            }
        config.device = device
        config.save(update_fields=["device"])
        linked_config = config

    msg = f"Created device #{device.deviceid} ({name})"
    if linked_config:
        msg += f" and linked it to configuration #{linked_config.configid}"
    return {"success": True, "message": msg + "."}


def _handle_publication_upload(request):
    runid = request.POST.get("runid", "").strip()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    doi = request.POST.get("doi", "").strip()
    citation = request.POST.get("citation", "").strip()

    if doi:
        # Deduplicate by DOI — reuse existing publication if the DOI already exists
        pub, created = Publication.objects.get_or_create(
            DOI=doi,
            defaults={
                "correspauthor_firstname": first_name,
                "correspauthor_lastname": last_name,
                "citation": citation,
            },
        )
    else:
        pub = Publication.objects.create(
            correspauthor_firstname=first_name,
            correspauthor_lastname=last_name,
            DOI="",
            citation=citation,
        )
        created = True

    if runid:
        try:
            desc_run = DescRun.objects.get(descrunid=int(runid))
            desc_run.publication = pub
            desc_run.save(update_fields=["publication"])
        except (DescRun.DoesNotExist, ValueError):
            return {"success": False, "message": f"DESC Run ID {runid} not found."}

    action = "Created" if created else "Found existing"
    linked = f" and linked it to DESC Run #{runid}" if runid else ""
    return {
        "success": True,
        "message": f"{action} publication #{pub.publicationid}{linked}.",
    }


# ---------------------------------------------------------------------------
# Query helpers — column definitions
# ---------------------------------------------------------------------------

# _OUTPUT_COLUMNS[table] maps table names to column lists.
# The group whose key == table name holds the main (filterable) columns.
# Other keys are related tables whose columns can be included in SELECT.
_OUTPUT_COLUMNS = {
    "desc_runs": {
        "desc_runs": [
            "descrunid",
            "configid",
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
        "configurations": [
            "configurations.name",
            "configurations.NFP",
            "configurations.classification",
            "configurations.stell_sym",
            "configurations.aspect_ratio",
            "configurations.major_radius",
            "configurations.minor_radius",
            "configurations.volume",
            "configurations.volume_averaged_beta",
            "configurations.volume_averaged_B",
            "configurations.total_toroidal_current",
        ],
        "devices": [
            "devices.name",
        ],
        "publications": [
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
            "classification",
            "date_created",
        ],
        "devices": [
            "devices.name",
        ],
        "desc_runs": [
            "descrunid",
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
        ],
        "vmec_runs": [
            "vmecrunid",
            "vmec_version",
            "mpol",
            "mtor",
        ],
    },
    "devices": {
        "devices": [
            "deviceid",
            "user_created",
            "name",
            "description",
            "date_created",
            "date_updated",
        ],
        "configurations": [
            "configurations.name",
            "configurations.NFP",
            "configurations.classification",
            "configurations.aspect_ratio",
            "configurations.major_radius",
        ],
        "desc_runs": [
            "descrunid",
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
        ],
        "vmec_runs": [
            "vmecrunid",
            "vmec_version",
            "mpol",
            "mtor",
        ],
    },
    "publications": {
        "publications": [
            "publicationid",
            "pub_label",
            "correspauthor_firstname",
            "correspauthor_lastname",
            "citation",
            "DOI",
        ],
        "desc_runs": [
            "descrunid",
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
        ],
        "vmec_runs": [
            "vmecrunid",
            "vmec_version",
            "mpol",
            "mtor",
        ],
    },
    "vmec_runs": {
        "vmec_runs": [
            "vmecrunid",
            "configid",
            "user_created",
            "description",
            "provenance",
            "vmec_version",
            "mpol",
            "mtor",
            "publicationid",
            "date_created",
        ],
        "configurations": [
            "configurations.name",
            "configurations.NFP",
            "configurations.classification",
            "configurations.stell_sym",
            "configurations.aspect_ratio",
            "configurations.major_radius",
            "configurations.minor_radius",
        ],
        "devices": [
            "devices.name",
        ],
        "publications": [
            "publications.publicationid",
            "publications.correspauthor_firstname",
            "publications.correspauthor_lastname",
            "publications.DOI",
            "publications.citation",
        ],
        "desc_runs": [
            "descrunid",
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
        ],
    },
}

_JOINS = {
    "desc_runs": [
        "LEFT JOIN configurations ON desc_runs.configid = configurations.configid",
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
        "LEFT JOIN vmec_runs ON configurations.configid = vmec_runs.configid",
        "LEFT JOIN publications ON desc_runs.publicationid = publications.publicationid",
    ],
    "configurations": [
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
        "LEFT JOIN desc_runs ON configurations.configid = desc_runs.configid",
        "LEFT JOIN vmec_runs ON configurations.configid = vmec_runs.configid",
    ],
    "devices": [
        "LEFT JOIN configurations ON devices.deviceid = configurations.deviceid",
        "LEFT JOIN desc_runs ON configurations.configid = desc_runs.configid",
        "LEFT JOIN vmec_runs ON configurations.configid = vmec_runs.configid",
    ],
    "publications": [
        "LEFT JOIN desc_runs ON publications.publicationid = desc_runs.publicationid",
        "LEFT JOIN vmec_runs ON publications.publicationid = vmec_runs.publicationid",
    ],
    "vmec_runs": [
        "LEFT JOIN configurations ON vmec_runs.configid = configurations.configid",
        "LEFT JOIN desc_runs ON vmec_runs.configid = desc_runs.configid",
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
