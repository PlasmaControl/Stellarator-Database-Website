from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Extended user model with admin-approval workflow."""
    is_approved = models.BooleanField(
        default=False,
        help_text='Admin must approve this account before the user can upload or query data.'
    )
    institution = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"


class Device(models.Model):
    deviceid = models.AutoField(primary_key=True)
    user_created = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    device_class = models.CharField(max_length=50, blank=True, db_column='class')
    NFP = models.IntegerField(null=True, blank=True)
    stell_sym = models.BooleanField(null=True, blank=True)
    date_created = models.DateField(null=True, blank=True)
    date_updated = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'devices'

    def __str__(self):
        return self.name or f"Device #{self.deviceid}"


class Configuration(models.Model):
    configid = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    device = models.ForeignKey(
        Device, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='deviceid'
    )
    user_created = models.CharField(max_length=100, blank=True)
    NFP = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    provenance = models.CharField(max_length=200, blank=True)
    m = models.TextField(blank=True)
    n = models.TextField(blank=True)
    stell_sym = models.BooleanField(null=True, blank=True)
    toroidal_flux = models.FloatField(null=True, blank=True)
    aspect_ratio = models.FloatField(null=True, blank=True)
    major_radius = models.FloatField(null=True, blank=True)
    minor_radius = models.FloatField(null=True, blank=True)
    volume = models.FloatField(null=True, blank=True)
    volume_averaged_beta = models.FloatField(null=True, blank=True)
    volume_averaged_B = models.FloatField(null=True, blank=True)
    total_toroidal_current = models.FloatField(null=True, blank=True)
    RBC = models.TextField(blank=True)
    ZBS = models.TextField(blank=True)
    RBS = models.TextField(blank=True)
    ZBC = models.TextField(blank=True)
    current_specification = models.CharField(max_length=100, blank=True)
    pressure_profile_type = models.CharField(max_length=100, blank=True)
    pressure_profile_data1 = models.TextField(blank=True)
    pressure_profile_data2 = models.TextField(blank=True)
    current_profile_type = models.CharField(max_length=100, blank=True)
    current_profile_data1 = models.TextField(blank=True)
    current_profile_data2 = models.TextField(blank=True)
    iota_profile_type = models.CharField(max_length=100, blank=True)
    iota_profile_data1 = models.TextField(blank=True)
    iota_profile_data2 = models.TextField(blank=True)
    average_elongation = models.FloatField(null=True, blank=True)
    Z_excursion = models.FloatField(null=True, blank=True)
    R_excursion = models.FloatField(null=True, blank=True)
    config_class = models.CharField(max_length=50, blank=True, db_column='class')
    date_created = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'configurations'

    def __str__(self):
        return self.name or f"Config #{self.configid}"


class Publication(models.Model):
    publicationid = models.CharField(max_length=100, primary_key=True)
    correspauthor_firstname = models.CharField(max_length=100, blank=True)
    correspauthor_lastname = models.CharField(max_length=100, blank=True)
    citation = models.TextField(blank=True)
    DOI = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'publications'

    def __str__(self):
        return self.publicationid


class DescRun(models.Model):
    descrunid = models.AutoField(primary_key=True)
    config_name = models.ForeignKey(
        Configuration, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='config_name', to_field='name'
    )
    user_created = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    provenance = models.CharField(max_length=200, blank=True)
    version = models.CharField(max_length=50, blank=True)
    initialization_method = models.CharField(max_length=200, blank=True)
    l_rad = models.IntegerField(null=True, blank=True)
    m_pol = models.IntegerField(null=True, blank=True)
    n_tor = models.IntegerField(null=True, blank=True)
    l_grid = models.IntegerField(null=True, blank=True)
    m_grid = models.IntegerField(null=True, blank=True)
    n_grid = models.IntegerField(null=True, blank=True)
    inputfilename = models.CharField(max_length=200, blank=True)
    outputfile = models.CharField(max_length=200, blank=True)
    profile_rho = models.TextField(blank=True)
    current_specification = models.CharField(max_length=100, blank=True)
    iota_profile = models.TextField(blank=True)
    iota_max = models.FloatField(null=True, blank=True)
    iota_min = models.FloatField(null=True, blank=True)
    current_profile = models.TextField(blank=True)
    pressure_profile = models.TextField(blank=True)
    pressure_max = models.FloatField(null=True, blank=True)
    pressure_min = models.FloatField(null=True, blank=True)
    D_Mercier = models.TextField(blank=True)
    D_Mercier_min = models.FloatField(null=True, blank=True)
    D_Mercier_max = models.FloatField(null=True, blank=True)
    publicationid = models.ForeignKey(
        Publication, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='publicationid', to_field='publicationid'
    )
    date_created = models.DateField(null=True, blank=True)
    vacuum = models.BooleanField(null=True, blank=True)
    spectral_indexing = models.CharField(max_length=50, blank=True)
    sym = models.BooleanField(null=True, blank=True)
    surface_plot = models.CharField(max_length=200, blank=True)
    boozer_plot = models.CharField(max_length=200, blank=True)
    plot3d = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'desc_runs'

    def __str__(self):
        return f"DescRun #{self.descrunid}"


class VmecRun(models.Model):
    vmecrunid = models.AutoField(primary_key=True)
    config_name = models.ForeignKey(
        Configuration, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='config_name', to_field='name'
    )
    user_created = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    provenance = models.CharField(max_length=200, blank=True)
    vmec_version = models.CharField(max_length=50, blank=True)
    mpol = models.IntegerField(null=True, blank=True)
    mtor = models.IntegerField(null=True, blank=True)
    ns_array = models.TextField(blank=True)
    niter_array = models.TextField(blank=True)
    ftol_array = models.TextField(blank=True)
    iotaf = models.TextField(blank=True)
    inputfile = models.CharField(max_length=200, blank=True)
    outputfile = models.CharField(max_length=200, blank=True)
    publicationid = models.ForeignKey(
        Publication, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='publicationid', to_field='publicationid'
    )
    date_created = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'vmec_runs'

    def __str__(self):
        return f"VmecRun #{self.vmecrunid}"
