# Generated by Django 3.2.16 on 2025-03-04 12:52

from django.db import migrations, models
import django.db.models.expressions


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_auto_20250304_1516'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='subscription',
            name='taboo_self_follow',
        ),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.CheckConstraint(check=models.Q(('user', django.db.models.expressions.F('author')), _negated=True), name='taboo_self_follow'),
        ),
    ]
