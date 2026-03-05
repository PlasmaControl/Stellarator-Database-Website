from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required.')
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    institution = forms.CharField(
        max_length=200, required=True,
        help_text='University or research institution.'
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'institution', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.institution = self.cleaned_data['institution']
        user.is_approved = False  # requires admin approval
        if commit:
            user.save()
        return user
