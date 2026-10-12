from django.db import migrations, models
import django.db.models.deletion
import core.routing


def populate_slugs(apps, schema_editor):
    Customer = apps.get_model("core", "Customer")
    used = set()
    for customer in Customer.objects.using(schema_editor.connection.alias).order_by("pk").iterator():
        base = "org-" + customer.identifier.lower()
        slug = base if base not in used else f"{base}-{customer.pk}"
        used.add(slug)
        Customer.objects.using(schema_editor.connection.alias).filter(pk=customer.pk).update(slug=slug)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_alter_customer_phone")]
    operations = [
        migrations.AddField(
            model_name="customer", name="slug", field=models.SlugField(max_length=48, null=True, unique=True)
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customer",
            name="slug",
            field=models.SlugField(
                default=core.routing.generate_slug,
                max_length=48,
                unique=True,
                validators=[core.routing.validate_portal_slug],
            ),
        ),
        migrations.AddField(
            model_name="customer", name="capacity", field=models.PositiveIntegerField(blank=True, null=True)
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.CheckConstraint(
                condition=models.Q(capacity__isnull=True) | models.Q(capacity__gt=0), name="capacity_positive"
            ),
        ),
        migrations.RemoveConstraint(model_name="user", name="user_valid_role"),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("super_admin", "مدیر ارشد"),
                    ("admin", "مدیر"),
                    ("operator", "اپراتور"),
                    ("tenant", "کاربر مجموعه"),
                ],
                db_index=True,
                default="operator",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="portal_accounts",
                to="core.customer",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="portal_username",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="user", name="is_portal_owner", field=models.BooleanField(default=False)
        ),
        migrations.AddField(
            model_name="user", name="portal_session_version", field=models.PositiveIntegerField(default=0)
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=["super_admin", "admin", "operator", "tenant"]),
                name="user_valid_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(role="tenant", organization__isnull=False) & ~models.Q(portal_username=""))
                    | (
                        models.Q(organization__isnull=True, portal_username="", is_portal_owner=False)
                        & ~models.Q(role="tenant")
                    )
                ),
                name="user_authentication_realm",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["organization", "portal_username"], name="organization_unique_login"
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_portal_owner=True),
                name="organization_one_owner",
            ),
        ),
    ]
