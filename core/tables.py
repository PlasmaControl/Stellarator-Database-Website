"""
Unified schema and Django model definitions for all database tables.

Each field in the schema lists is a tuple: (column_name, type, description)
  - column_name : DB column name, same as CSV column name
  - type        : 'str'   -> CharField(max_length=200, blank=True)
                  'text'  -> TextField(blank=True)
                  'int'   -> IntegerField(null=True, blank=True)
                  'float' -> FloatField(null=True, blank=True)
                  'bool'  -> BooleanField(null=True, blank=True)
                  None    -> system-set (PK, FK, date, user) — not parsed from CSV
  - description : human-readable text for the data description page

RENAMES maps the few column names that are Python reserved words to their Django
model attribute names (e.g. 'class' -> 'device_class').

To add a new field:
  1. Add it here in the correct table list with the right type.
  2. Run makemigrations / migrate.
  CSV parsing, data description page, and type casting all update automatically.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

DEVICE_FIELDS = [
    ("deviceid", None, "Unique identifier of the device"),
    ("user_created", None, "User who created this device in the database"),
    ("name", "str", "Name of the device"),
    ("description", "text", "Description of the device"),
    ("date_created", None, "The date device is saved to the database (YY/MM/DD)"),
    ("date_updated", None, "The date device is updated (YY/MM/DD)"),
]

CONFIG_FIELDS = [
    ("configid", None, "Unique identifier for the configuration"),
    ("name", "str", "Unique name for the configuration"),
    (
        "deviceid",
        None,
        "Unique identifier of the device that this configuration represents, if there is any",
    ),
    (
        "user_created",
        None,
        "Full name of the user who created this configuration in database",
    ),
    ("NFP", "int", "Number of field periods (integer)"),
    ("description", "text", "Description of this configuration"),
    (
        "provenance",
        "str",
        "Short description of where this configuration came from, e.g. DESC github repo",
    ),
    ("m", "text", "Poloidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS"),
    ("n", "text", "Toroidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS"),
    ("stell_sym", "bool", "1 if the configuration is stellarator symmetric, 0 if not"),
    ("toroidal_flux", "float", "Total toroidal flux Psi"),
    (
        "aspect_ratio",
        "float",
        "Aspect ratio found by average major radius over average minor radius",
    ),
    ("major_radius", "float", "Average major radius in meters"),
    ("minor_radius", "float", "Average minor radius in meters"),
    (
        "volume",
        "float",
        "Total volume enclosed by the last closed flux surface in cubic meters",
    ),
    ("volume_averaged_beta", "float", "Volume averaged normalized plasma pressure"),
    ("volume_averaged_B", "float", "Volume averaged magnetic field in Tesla"),
    (
        "total_toroidal_current",
        "float",
        "Net toroidal current enclosed by last closed flux surface in Amperes",
    ),
    ("RBC", "text", "Array of the R_mn cos(mt - nz) coefficients"),
    ("ZBS", "text", "Array of the Z_mn sin(mt - nz) coefficients"),
    ("RBS", "text", "Array of the R_mn sin(mt - nz) coefficients"),
    ("ZBC", "text", "Array of the Z_mn cos(mt - nz) coefficients"),
    (
        "current_specification",
        "str",
        "The given profile whether iota or net enclosed current",
    ),
    (
        "pressure_profile_type",
        "str",
        "The type of the given pressure profile, i.e. PowerSeriesProfile, SplineProfile",
    ),
    (
        "pressure_profile_data1",
        "text",
        "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).",
    ),
    (
        "pressure_profile_data2",
        "text",
        "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.",
    ),
    (
        "current_profile_type",
        "str",
        "The type of the given current profile (Note: only iota or current profile is given, not both)",
    ),
    (
        "current_profile_data1",
        "text",
        "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).",
    ),
    (
        "current_profile_data2",
        "text",
        "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.",
    ),
    (
        "iota_profile_type",
        "str",
        "The type of the given iota profile (Note: only iota or current profile is given, not both)",
    ),
    (
        "iota_profile_data1",
        "text",
        "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots).",
    ),
    (
        "iota_profile_data2",
        "text",
        "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values.",
    ),
    (
        "average_elongation",
        "float",
        "Average elongation, mean(major radius over minor radius)",
    ),
    (
        "Z_excursion",
        "float",
        "Measure of the excursion in the vertical direction (Z_max - Z_min)",
    ),
    (
        "R_excursion",
        "float",
        "Measure of the excursion in the radial direction (R_max - R_min)",
    ),
    (
        "classification",
        "str",
        "Class of the configuration: Axisymmetric (AS), Quasi-Axisymmetric (QA), Quasi-Helically Symmetric (QH), etc.",
    ),
    (
        "date_created",
        None,
        "The date the configuration was saved to the database (YY/MM/DD)",
    ),
]

DESC_RUN_FIELDS = [
    ("descrunid", None, "Unique identifier for the desc_run"),
    (
        "configid",
        None,
        "Integer FK to the configuration used to generate this desc_run (further details in the configurations table)",
    ),
    (
        "user_created",
        None,
        "Full name of the user who created this desc_run in the database",
    ),
    ("description", "text", "Description of the desc_run"),
    (
        "provenance",
        "str",
        "Short description of where this configuration and desc run came from, e.g. DESC github repo",
    ),
    ("version", "str", "DESC version used for this simulation"),
    (
        "initialization_method",
        "str",
        'The method of how the DESC equilibrium solution was initialized — one of "surface", "NAE", "poincare_section", or the name of a .nc or .h5 file corresponding to a VMEC (if .nc) or DESC (if .h5) solution',
    ),
    ("l_rad", "int", "Radial spectral resolution"),
    ("m_pol", "int", "Poloidal spectral resolution"),
    ("n_tor", "int", "Toroidal spectral resolution"),
    ("l_grid", "int", "Radial grid resolution (usually double the l_rad)"),
    ("m_grid", "int", "Poloidal grid resolution (usually double the m_pol)"),
    ("n_grid", "int", "Toroidal grid resolution (usually double the n_tor)"),
    (
        "inputfilename",
        "str",
        'The name of the input file (if any) used to generate the equilibrium. The ones that have "auto_generated_" prefix are automatically generated by DESC.',
    ),
    ("outputfile", "str", "The name of the output file as stored in the database."),
    (
        "profile_rho",
        "text",
        "rho values used to evaluate iota, current and pressure profiles for the database",
    ),
    (
        "current_specification",
        "str",
        'If the total enclosed current is given as a profile then this has "net enclosed current" value, if the iota profile is given then "iota"',
    ),
    (
        "iota_profile",
        "text",
        "Iota profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1",
    ),
    (
        "iota_max",
        "float",
        "The maximum value of iota calculated on an evenly spaced rho grid of 101 points",
    ),
    (
        "iota_min",
        "float",
        "The minimum value of iota calculated on an evenly spaced rho grid of 101 points",
    ),
    (
        "current_profile",
        "text",
        "Current profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1",
    ),
    (
        "pressure_profile",
        "text",
        "Pressure profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1",
    ),
    (
        "pressure_max",
        "float",
        "The maximum value of pressure calculated on an evenly spaced rho grid of 101 points",
    ),
    (
        "pressure_min",
        "float",
        "The minimum value of pressure calculated on an evenly spaced rho grid of 101 points",
    ),
    (
        "D_Mercier",
        "text",
        "Mercier stability criterion evaluated at 11 evenly spaced radial points from rho=0.1 to rho=1 (positive/negative value denotes stability/instability)",
    ),
    ("D_Mercier_min", "float", "The minimum value of D_Mercier"),
    ("D_Mercier_max", "float", "The maximum value of D_Mercier"),
    ("vacuum", "bool", "True if the equilibrium is vacuum (no pressure or current)"),
    ("spectral_indexing", "str", "Spectral indexing method used"),
    ("sym", "bool", "True if the equilibrium is symmetric"),
    (
        "publicationid",
        None,
        "ID of the publication (as stored in the database) if there is any",
    ),
    ("date_created", None, "The date the run was saved to the database (YY/MM/DD)"),
]

VMEC_RUN_FIELDS = [
    ("vmecrunid", None, "Unique identifier for the vmec_run"),
    ("configid", None, "Integer FK to the configuration used for this VMEC run"),
    ("user_created", None, "User who created this VMEC run in the database"),
    ("description", "text", "Description of the VMEC run"),
    ("provenance", "str", "Short description of where this VMEC run came from"),
    ("vmec_version", "str", "VMEC version used for this simulation"),
    ("mpol", "int", "Poloidal mode number"),
    ("mtor", "int", "Toroidal mode number"),
    ("ns_array", "text", "Array of radial grid points"),
    ("niter_array", "text", "Array of maximum iterations"),
    ("ftol_array", "text", "Array of force tolerance"),
    ("iotaf", "text", "Iota profile on full grid"),
    ("inputfile", "str", "Name of the input file"),
    ("outputfile", "str", "Name of the output file"),
    ("publicationid", None, "ID of associated publication if any"),
    ("date_created", None, "Date the run was saved to the database"),
]

PUBLICATION_FIELDS = [
    ("publicationid", None, "Auto-assigned integer identifier for the publication"),
    (
        "pub_label",
        "str",
        "Optional user-assigned label for this publication (e.g. 'Smith2023')",
    ),
    ("correspauthor_firstname", None, "First name of the corresponding author"),
    ("correspauthor_lastname", None, "Last name of the corresponding author"),
    ("citation", None, "Citation of the publication"),
    ("DOI", None, "Digital Object Identifier (DOI) — a unique key for the publication"),
]


# ---------------------------------------------------------------------------
# Field factory — builds Django field instances from schema types
# ---------------------------------------------------------------------------


def _make_field(dtype, **kwargs):
    """Return a Django model field for the given schema type string."""
    if dtype == "str":
        return models.CharField(max_length=200, blank=True, **kwargs)
    if dtype == "text":
        return models.TextField(blank=True, **kwargs)
    if dtype == "int":
        return models.IntegerField(null=True, blank=True, **kwargs)
    if dtype == "float":
        return models.FloatField(null=True, blank=True, **kwargs)
    if dtype == "bool":
        return models.BooleanField(null=True, blank=True, **kwargs)
    raise ValueError(f"Unknown schema type: {dtype!r}")


def _schema_to_fields(field_list, renames=None, skip=()):
    """
    Convert a schema list to a dict of {attr_name: django_field}.
    Skips None-typed (system-set) fields and any column names in *skip*.
    Applies RENAMES and sets db_column when the attribute name differs from the
    column name (e.g. 'class' -> device_class with db_column='class').
    """
    renames = renames or {}
    result = {}
    for col, dtype, _ in field_list:
        if dtype is None or col in skip:
            continue
        attr = renames.get(col, col)
        extra = {"db_column": col} if col != attr else {}
        result[attr] = _make_field(dtype, **extra)
    return result


# ---------------------------------------------------------------------------
# User — extends AbstractUser; kept as a regular class (too special to generate)
# ---------------------------------------------------------------------------


class User(AbstractUser):
    """Extended user model with admin-approval workflow."""

    is_approved = models.BooleanField(
        default=False,
        help_text="Admin must approve this account before the user can upload or query data.",
    )
    institution = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

Device = type(
    "Device",
    (models.Model,),
    {
        "__module__": __name__,
        # System-set fields (None in schema)
        "deviceid": models.AutoField(primary_key=True),
        "user_created": models.CharField(max_length=100, blank=True),
        "date_created": models.DateField(null=True, blank=True),
        "date_updated": models.DateField(null=True, blank=True),
        # Schema-driven fields (str/text/int/bool)
        **_schema_to_fields(DEVICE_FIELDS),
        # Meta & helpers
        "Meta": type("Meta", (), {"db_table": "devices"}),
        "__str__": lambda self: self.name or f"Device #{self.deviceid}",
    },
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

Configuration = type(
    "Configuration",
    (models.Model,),
    {
        "__module__": __name__,
        # System-set fields (None in schema)
        "configid": models.AutoField(primary_key=True),
        "name": models.CharField(max_length=200, blank=True, null=True),
        "device": models.ForeignKey(
            Device,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            db_column="deviceid",
        ),
        "user_created": models.CharField(max_length=100, blank=True),
        "date_created": models.DateField(null=True, blank=True),
        # Schema-driven fields (skip 'name' — defined above)
        **_schema_to_fields(CONFIG_FIELDS, skip={"name"}),
        # Meta & helpers
        "Meta": type("Meta", (), {"db_table": "configurations"}),
        "__str__": lambda self: self.name or f"Config #{self.configid}",
    },
)


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

Publication = type(
    "Publication",
    (models.Model,),
    {
        "__module__": __name__,
        "publicationid": models.AutoField(primary_key=True),
        "pub_label": models.CharField(max_length=200, blank=True),
        "correspauthor_firstname": models.CharField(max_length=100, blank=True),
        "correspauthor_lastname": models.CharField(max_length=100, blank=True),
        "citation": models.TextField(blank=True),
        "DOI": models.CharField(max_length=200, blank=True),
        "Meta": type("Meta", (), {"db_table": "publications"}),
        "__str__": lambda self: self.pub_label or f"Publication #{self.publicationid}",
    },
)


# ---------------------------------------------------------------------------
# DescRun
# ---------------------------------------------------------------------------

DescRun = type(
    "DescRun",
    (models.Model,),
    {
        "__module__": __name__,
        # System-set fields (None in schema)
        "descrunid": models.AutoField(primary_key=True),
        "config": models.ForeignKey(
            Configuration,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            db_column="configid",
        ),
        "user_created": models.CharField(max_length=100, blank=True),
        "publication": models.ForeignKey(
            Publication,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            db_column="publicationid",
        ),
        "date_created": models.DateField(null=True, blank=True),
        # File path fields (not in schema — set by the upload pipeline)
        "surface_plot": models.CharField(max_length=200, blank=True),
        "boozer_plot": models.CharField(max_length=200, blank=True),
        "plot3d": models.CharField(max_length=200, blank=True),
        # Schema-driven fields
        **_schema_to_fields(DESC_RUN_FIELDS),
        # Meta & helpers
        "Meta": type("Meta", (), {"db_table": "desc_runs"}),
        "__str__": lambda self: f"DescRun #{self.descrunid}",
    },
)


# ---------------------------------------------------------------------------
# VmecRun
# ---------------------------------------------------------------------------

VmecRun = type(
    "VmecRun",
    (models.Model,),
    {
        "__module__": __name__,
        # System-set fields (None in schema)
        "vmecrunid": models.AutoField(primary_key=True),
        "config": models.ForeignKey(
            Configuration,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            db_column="configid",
        ),
        "user_created": models.CharField(max_length=100, blank=True),
        "publication": models.ForeignKey(
            Publication,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            db_column="publicationid",
        ),
        "date_created": models.DateField(null=True, blank=True),
        # Schema-driven fields
        **_schema_to_fields(VMEC_RUN_FIELDS),
        # Meta & helpers
        "Meta": type("Meta", (), {"db_table": "vmec_runs"}),
        "__str__": lambda self: f"VmecRun #{self.vmecrunid}",
    },
)
