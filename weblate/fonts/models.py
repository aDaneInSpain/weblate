# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2019 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from weblate.fonts.utils import get_font_name
from weblate.fonts.validators import validate_font
from weblate.lang.models import Language
from weblate.trans.mixins import UserDisplayMixin
from weblate.trans.models import Project
from weblate.utils.data import data_dir

FONT_STORAGE = FileSystemStorage(location=data_dir("fonts"))


@python_2_unicode_compatible
class Font(models.Model, UserDisplayMixin):
    family = models.CharField(verbose_name=_("Font family"), max_length=100, blank=True)
    style = models.CharField(verbose_name=_("Font style"), max_length=100, blank=True)
    font = models.FileField(
        verbose_name=_("Font file"),
        validators=[validate_font],
        storage=FONT_STORAGE,
        help_text=_("OpenType and TrueType fonts are supported."),
    )
    project = models.ForeignKey(Project, on_delete=models.deletion.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.deletion.SET_NULL,
    )

    class Meta(object):
        unique_together = [("family", "style", "project")]

    def __init__(self, *args, **kwargs):
        super(Font, self).__init__(*args, **kwargs)
        self.field_errors = {}

    def __str__(self):
        return "{} {}".format(self.family, self.style)

    def get_absolute_url(self):
        return reverse("font", kwargs={"pk": self.pk, "project": self.project.slug})

    def clean_fields(self, exclude=None):
        self.field_errors = {}
        try:
            super(Font, self).clean_fields(exclude)
        except ValidationError as error:
            self.field_errors = error.error_dict
            raise

    def clean(self):
        # Try to parse file only if it passed validation
        if "font" not in self.field_errors and not self.family:
            self.family, self.style = get_font_name(self.font)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        self.clean()
        super(Font, self).save(force_insert, force_update, using, update_fields)

    def get_usage(self):
        related = FontGroup.objects.filter(
            models.Q(font=self) | models.Q(fontoverride__font=self)
        )
        return related.order().distinct()


class FontGroupQuerySet(models.QuerySet):
    def order(self):
        return self.order_by("name")


@python_2_unicode_compatible
class FontGroup(models.Model):
    name = models.SlugField(
        verbose_name=_("Font group name"),
        max_length=100,
        help_text=_(
            "Identifier you will use in checks to select this font group. "
            "Avoid whitespace or special characters."
        ),
    )
    font = models.ForeignKey(
        Font,
        verbose_name=_("Default font"),
        on_delete=models.deletion.CASCADE,
        help_text=_("Default font is used unless per language override matches."),
    )
    project = models.ForeignKey(Project, on_delete=models.deletion.CASCADE)

    objects = FontGroupQuerySet.as_manager()

    class Meta(object):
        unique_together = [("name", "project")]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "font_group", kwargs={"pk": self.pk, "project": self.project.slug}
        )


@python_2_unicode_compatible
class FontOverride(models.Model):
    group = models.ForeignKey(FontGroup, on_delete=models.deletion.CASCADE)
    font = models.ForeignKey(
        Font, on_delete=models.deletion.CASCADE, verbose_name=_("Font")
    )
    language = models.ForeignKey(
        Language, on_delete=models.deletion.CASCADE, verbose_name=_("Language")
    )

    class Meta(object):
        unique_together = [("group", "language")]

    def __str__(self):
        return "{}:{}:{}".format(self.group, self.font, self.language)
