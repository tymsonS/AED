# AEDane (HackNation 2026): flaga zasobu AED i wskazanie wykazu zbiorczego AED.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0075_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="contains_aed_data",
            field=models.BooleanField(default=False, verbose_name="Zawiera wykaz defibrylatorów AED"),
        ),
        migrations.CreateModel(
            name="AggregatedAEDInfo",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "resource",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to="resources.Resource"
                    ),
                ),
            ],
        ),
    ]
