from django.db import migrations


MEDICAL_REASONS = [
    ("dor", "Dor", "痛み"),
    ("febre", "Febre", "発熱"),
    ("mal_estar", "Mal-estar", "体調不良"),
    ("acidente", "Acidente", "事故"),
    ("alergia", "Alergia", "アレルギー"),
    ("outros", "Outros", "その他"),
]

SYMPTOM_TYPES = [
    ("dor_de_cabeca", "Dor de cabeca", "頭痛"),
    ("febre", "Febre", "発熱"),
    ("tontura", "Tontura", "めまい"),
    ("nausea", "Nausea", "吐き気"),
    ("dor_corporal", "Dor corporal", "体の痛み"),
    ("tosse", "Tosse", "咳"),
    ("dificuldade_respiratoria", "Dificuldade respiratoria", "呼吸困難"),
    ("outros", "Outros", "その他"),
]


def seed_medical_master_data(apps, schema_editor):
    MedicalReason = apps.get_model("medical", "MedicalReason")
    SymptomType = apps.get_model("medical", "SymptomType")

    for code, name_pt, name_jp in MEDICAL_REASONS:
        MedicalReason.objects.get_or_create(
            code=code,
            defaults={
                "name_pt": name_pt,
                "name_jp": name_jp,
                "is_active": True,
            },
        )

    for code, name_pt, name_jp in SYMPTOM_TYPES:
        SymptomType.objects.get_or_create(
            code=code,
            defaults={
                "name_pt": name_pt,
                "name_jp": name_jp,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("medical", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_medical_master_data, migrations.RunPython.noop),
    ]
