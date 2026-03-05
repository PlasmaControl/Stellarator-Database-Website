"""
Central schema definitions for all database tables.

Each field is a tuple: (column_name, type, description)
  - column_name : DB column name, also the CSV column name (they are the same)
  - type        : 'str' | 'int' | 'float' | 'bool' | None
                  None = system-set (auto PK, session user, today's date, FK resolved
                  separately) — field appears in data descriptions but is NOT parsed
                  from CSV by _fields_from_csv.
  - description : human-readable text for the data description page

RENAMES maps the few column names that are Python reserved words to their Django
model attribute names (e.g. 'class' -> 'device_class').  All other attributes
share the column name exactly.

To add a new field:
  1. Add it here in the correct table list.
  2. Add the matching field to the Django model in models.py.
  3. Run makemigrations / migrate.
  CSV parsing, data description page, and type casting all update automatically.
"""

# ---------------------------------------------------------------------------
# Rename maps: column_name -> Django model attribute name
# Only needed where the column name is a Python keyword.
# ---------------------------------------------------------------------------

DEVICE_RENAMES = {"class": "device_class"}
CONFIG_RENAMES = {"class": "config_class"}

# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

DEVICE_FIELDS = [
    ("deviceid",     None,   "Unique identifier of the device"),
    ("user_created", None,   "User who created this device in the database"),
    ("name",         "str",  "Name of the device"),
    ("description",  "str",  "Description of the device"),
    ("class",        "str",  "Class of the device: Axisymmetric (AS), Quasi-Axisymmetric (QA), Quasi-Helically Symmetric (QH), etc."),
    ("NFP",          "int",  "Number of field periods (integer)"),
    ("stell_sym",    "bool", "1 if the device is stellarator symmetric, 0 if not"),
    ("date_created", None,   "The date device is saved to the database (YY/MM/DD)"),
    ("date_updated", None,   "The date device is updated (YY/MM/DD)"),
]

# ---------------------------------------------------------------------------
# configurations
# ---------------------------------------------------------------------------

CONFIG_FIELDS = [
    ("configid",              None,    "Unique identifier for the configuration"),
    ("name",                  "str",   "Unique name for the configuration"),
    ("deviceid",              None,    "Unique identifier of the device that this configuration represents, if there is any"),
    ("user_created",          None,    "Full name of the user who created this configuration in database"),
    ("NFP",                   "int",   "Number of field periods (integer)"),
    ("description",           "str",   "Description of this configuration"),
    ("provenance",            "str",   "Short description of where this configuration came from, e.g. DESC github repo"),
    ("m",                     "str",   "Poloidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS"),
    ("n",                     "str",   "Toroidal modenumbers which correspond to the RBC/ZBC/RBS/ZBS"),
    ("stell_sym",             "bool",  "1 if the configuration is stellarator symmetric, 0 if not"),
    ("toroidal_flux",         "float", "Total toroidal flux Psi"),
    ("aspect_ratio",          "float", "Aspect ratio found by average major radius over average minor radius"),
    ("major_radius",          "float", "Average major radius in meters"),
    ("minor_radius",          "float", "Average minor radius in meters"),
    ("volume",                "float", "Total volume enclosed by the last closed flux surface in cubic meters"),
    ("volume_averaged_beta",  "float", "Volume averaged normalized plasma pressure"),
    ("volume_averaged_B",     "float", "Volume averaged magnetic field in Tesla"),
    ("total_toroidal_current","float", "Net toroidal current enclosed by last closed flux surface in Amperes"),
    ("RBC",                   "str",   "Array of the R_mn cos(mt - nz) coefficients"),
    ("ZBS",                   "str",   "Array of the Z_mn sin(mt - nz) coefficients"),
    ("RBS",                   "str",   "Array of the R_mn sin(mt - nz) coefficients"),
    ("ZBC",                   "str",   "Array of the Z_mn cos(mt - nz) coefficients"),
    ("current_specification", "str",   "The given profile whether iota or net enclosed current"),
    ("pressure_profile_type", "str",   "The type of the given pressure profile, i.e. PowerSeriesProfile, SplineProfile"),
    ("pressure_profile_data1","str",   "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots)."),
    ("pressure_profile_data2","str",   "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values."),
    ("current_profile_type",  "str",   "The type of the given current profile (Note: only iota or current profile is given, not both)"),
    ("current_profile_data1", "str",   "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots)."),
    ("current_profile_data2", "str",   "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values."),
    ("iota_profile_type",     "str",   "The type of the given iota profile (Note: only iota or current profile is given, not both)"),
    ("iota_profile_data1",    "str",   "If not a spline: modes of the series. If spline: 1-D array of independent variable values (knots)."),
    ("iota_profile_data2",    "str",   "If not a spline: coefficients of the series. If spline: 1-D array of dependent variable values."),
    ("average_elongation",    "float", "Average elongation, mean(major radius over minor radius)"),
    ("Z_excursion",           "float", "Measure of the excursion in the vertical direction (Z_max - Z_min)"),
    ("R_excursion",           "float", "Measure of the excursion in the radial direction (R_max - R_min)"),
    ("class",                 "str",   "Class of the configuration: Axisymmetric (AS), Quasi-Axisymmetric (QA), Quasi-Helically Symmetric (QH), etc."),
    ("date_created",          None,    "The date the configuration was saved to the database (YY/MM/DD)"),
]

# ---------------------------------------------------------------------------
# desc_runs
# ---------------------------------------------------------------------------

DESC_RUN_FIELDS = [
    ("descrunid",             None,    "Unique identifier for the desc_run"),
    ("config_name",           None,    "Unique identifier for the configuration used to generate this desc_run (further details in the configurations table)"),
    ("user_created",          None,    "Full name of the user who created this desc_run in the database"),
    ("description",           "str",   "Description of the desc_run"),
    ("provenance",            "str",   "Short description of where this configuration and desc run came from, e.g. DESC github repo"),
    ("version",               "str",   "DESC version used for this simulation"),
    ("initialization_method", "str",   'The method of how the DESC equilibrium solution was initialized — one of "surface", "NAE", "poincare_section", or the name of a .nc or .h5 file corresponding to a VMEC (if .nc) or DESC (if .h5) solution'),
    ("l_rad",                 "int",   "Radial spectral resolution"),
    ("m_pol",                 "int",   "Poloidal spectral resolution"),
    ("n_tor",                 "int",   "Toroidal spectral resolution"),
    ("l_grid",                "int",   "Radial grid resolution (usually double the l_rad)"),
    ("m_grid",                "int",   "Poloidal grid resolution (usually double the m_pol)"),
    ("n_grid",                "int",   "Toroidal grid resolution (usually double the n_tor)"),
    ("inputfilename",         "str",   'The name of the input file (if any) used to generate the equilibrium. The ones that have "auto_generated_" prefix are automatically generated by DESC.'),
    ("outputfile",            "str",   "The name of the output file as stored in the database."),
    ("profile_rho",           "str",   "rho values used to evaluate iota, current and pressure profiles for the database"),
    ("current_specification", "str",   'If the total enclosed current is given as a profile then this has "net enclosed current" value, if the iota profile is given then "iota"'),
    ("iota_profile",          "str",   "Iota profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1"),
    ("iota_max",              "float", "The maximum value of iota calculated on an evenly spaced rho grid of 101 points"),
    ("iota_min",              "float", "The minimum value of iota calculated on an evenly spaced rho grid of 101 points"),
    ("current_profile",       "str",   "Current profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1"),
    ("pressure_profile",      "str",   "Pressure profile evaluated at 11 evenly spaced flux surfaces between rho=0 and rho=1"),
    ("pressure_max",          "float", "The maximum value of pressure calculated on an evenly spaced rho grid of 101 points"),
    ("pressure_min",          "float", "The minimum value of pressure calculated on an evenly spaced rho grid of 101 points"),
    ("D_Mercier",             "str",   "Mercier stability criterion evaluated at 11 evenly spaced radial points from rho=0.1 to rho=1 (positive/negative value denotes stability/instability)"),
    ("D_Mercier_min",         "float", "The minimum value of D_Mercier"),
    ("D_Mercier_max",         "float", "The maximum value of D_Mercier"),
    ("vacuum",                "bool",  "True if the equilibrium is vacuum (no pressure or current)"),
    ("spectral_indexing",     "str",   "Spectral indexing method used"),
    ("sym",                   "bool",  "True if the equilibrium is symmetric"),
    ("publicationid",         None,    "ID of the publication (as stored in the database) if there is any"),
    ("date_created",          None,    "The date the run was saved to the database (YY/MM/DD)"),
]

# ---------------------------------------------------------------------------
# vmec_runs
# ---------------------------------------------------------------------------

VMEC_RUN_FIELDS = [
    ("vmecrunid",    None,  "Unique identifier for the vmec_run"),
    ("config_name",  None,  "Configuration used for this VMEC run"),
    ("user_created", None,  "User who created this VMEC run in the database"),
    ("description",  "str", "Description of the VMEC run"),
    ("provenance",   "str", "Short description of where this VMEC run came from"),
    ("vmec_version", "str", "VMEC version used for this simulation"),
    ("mpol",         "int", "Poloidal mode number"),
    ("mtor",         "int", "Toroidal mode number"),
    ("ns_array",     "str", "Array of radial grid points"),
    ("niter_array",  "str", "Array of maximum iterations"),
    ("ftol_array",   "str", "Array of force tolerance"),
    ("iotaf",        "str", "Iota profile on full grid"),
    ("inputfile",    "str", "Name of the input file"),
    ("outputfile",   "str", "Name of the output file"),
    ("publicationid",None,  "ID of associated publication if any"),
    ("date_created", None,  "Date the run was saved to the database"),
]

# ---------------------------------------------------------------------------
# publications
# ---------------------------------------------------------------------------

PUBLICATION_FIELDS = [
    ("publicationid",           None, "Unique identifier for the publication (string)"),
    ("correspauthor_firstname",  None, "First name of the corresponding author"),
    ("correspauthor_lastname",   None, "Last name of the corresponding author"),
    ("citation",                 None, "Citation of the publication"),
    ("DOI",                      None, "Digital Object Identifier (DOI) — a unique key for the publication"),
]
