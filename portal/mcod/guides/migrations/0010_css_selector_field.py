from django.db import migrations, models
import mcod.core.model_validators


class Migration(migrations.Migration):
    dependencies = [
        ("guides", "0009_auto_20241029_1508"),
    ]

    operations = [
        migrations.AlterField(
            model_name="guideitem",
            name="css_selector",
            field=models.CharField(
                max_length=300,
                validators=[mcod.core.model_validators.css_selector_validator],
                verbose_name="css selector",
            ),
        ),
    ]
