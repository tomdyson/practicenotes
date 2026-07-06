from django import forms

from .models import Set


class SetForm(forms.ModelForm):
    class Meta:
        model = Set
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "autofocus": True}),
            "description": forms.Textarea(
                attrs={"class": "input", "rows": 3, "placeholder": "Optional description"}
            ),
        }
