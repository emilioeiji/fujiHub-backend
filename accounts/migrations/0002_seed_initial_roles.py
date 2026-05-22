from django.db import migrations


INITIAL_ROLES = [
    ("Admin", "admin", "Acesso administrativo completo."),
    ("Escritorio", "escritorio", "Equipe administrativa do escritorio."),
    ("Supervisor", "supervisor", "Supervisores de operacao."),
    ("GL", "gl", "Group leaders."),
    ("KL", "kl", "Key leaders."),
    ("RH", "rh", "Recursos humanos."),
    ("Saude", "saude", "Equipe de atendimento medico e saude."),
    ("Almoxarifado", "almoxarifado", "Controle de estoque e uniformes."),
    ("Consulta", "consulta", "Acesso somente para consulta."),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for name, code, description in INITIAL_ROLES:
        Role.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "is_active": True,
            },
        )


def remove_seeded_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code__in=[code for _, code, _ in INITIAL_ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_roles, remove_seeded_roles),
    ]
