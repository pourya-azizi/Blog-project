# Generated by Django 3.2 on 2021-06-06 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_alter_category_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(max_length=20, null=True, unique=True),
        ),
    ]
