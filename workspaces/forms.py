from django import forms

from .models import Band, Owner
from .validators import validate_lowercase_slug, validate_not_reserved


class BandForm(forms.ModelForm):
    slug = forms.SlugField(
        label="URL name",
        max_length=50,
        validators=[validate_lowercase_slug, validate_not_reserved],
        help_text="Lowercase letters, numbers and hyphens. This claims your band's address.",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "quiet-ones"}),
    )

    class Meta:
        model = Band
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "The Quiet Ones", "autofocus": True}
            ),
        }

    def clean_slug(self):
        slug = self.cleaned_data["slug"].lower()
        if Owner.objects.filter(slug=slug).exists():
            raise forms.ValidationError("That name is already taken.")
        return slug


class BandRenameForm(forms.ModelForm):
    class Meta:
        model = Band
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "input"})}
