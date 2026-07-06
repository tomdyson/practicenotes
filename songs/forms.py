from django import forms

from .models import Item, Song


class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = ["title"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input", "autofocus": True}),
        }


class TextItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["title", "format", "body"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input", "placeholder": "Optional title, e.g. Lyrics"}
            ),
            "format": forms.Select(attrs={"class": "input"}),
            "body": forms.Textarea(
                attrs={
                    "class": "input font-mono text-sm",
                    "rows": 16,
                    "placeholder": "Lyrics, a chord chart, notes…",
                }
            ),
        }
        labels = {"body": "Text"}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Add some text.")
        return body
