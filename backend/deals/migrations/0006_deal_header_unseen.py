from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("deals", "0005_aiinteraction_humanaction_negotiationturn_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="deal",
            name="header_unseen",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddIndex(
            model_name="deal",
            index=models.Index(fields=["header_unseen", "status"], name="deals_deal_header__unseen_idx"),
        ),
    ]
