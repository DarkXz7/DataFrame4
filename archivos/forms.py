from django import forms
from .models import CarpetaCompartida

class CarpetaCompartidaForm(forms.ModelForm):
    class Meta:
        model = CarpetaCompartida
        fields = ['nombre', 'ruta', 'descripcion', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'ruta': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# Widget personalizado para múltiples archivos
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class SubirArchivoForm(forms.Form):
    archivo = MultipleFileField(
        label='Seleccionar archivos',
        help_text='Archivos soportados: .xlsx, .xls, .csv, .txt (máximo 10MB cada uno)',
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['archivo'].widget.attrs.update({
            'class': 'form-control',
            'accept': '.xlsx,.xls,.csv,.txt',
            'multiple': True
        })
    
    def clean_archivo(self):
        archivos = self.cleaned_data.get('archivo')
        
        if not archivos:
            raise forms.ValidationError('Debes seleccionar al menos un archivo')
        
        # Si es un solo archivo, convertir a lista
        if not isinstance(archivos, list):
            archivos = [archivos]
        
        for archivo in archivos:
            # Verificar extensión
            nombre = archivo.name.lower()
            if not nombre.endswith(('.xlsx', '.xls', '.csv', '.txt')):
                raise forms.ValidationError(f'Archivo {archivo.name}: Tipo no soportado. Use: .xlsx, .xls, .csv, .txt')
            
            # Verificar tamaño (10MB máximo)
            if archivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError(f'Archivo {archivo.name}: Demasiado grande. Máximo 10MB.')
        
        return archivos
    
    
    
class SQLUploadForm(forms.Form):
    MOTOR_CHOICES = [
        ('mysql', 'MySQL'),
        ('mariadb', 'MariaDB'),
    ]
    motor = forms.ChoiceField(choices=MOTOR_CHOICES, label="Motor de base de datos")
    usuario = forms.CharField(label="Usuario")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    host = forms.CharField(label="Host", initial="localhost")
    puerto = forms.IntegerField(label="Puerto", initial=3306)
    archivo_sql = forms.FileField(label="Archivo .sql")