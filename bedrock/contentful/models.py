from django.db import models
from django.utils.timezone import now

from contentful.resource_builder import ResourceBuilder
from django_extensions.db.fields.json import JSONField


class ContentfulEntryManager(models.Manager):
    def _get_page_obj(self, query):
        try:
            page_data = self.get(**query).data
        except ContentfulEntry.DoesNotExist:
            return None

        return ResourceBuilder('en-US', False, page_data).build()[0]

    def get_page_by_id(self, content_id):
        return self._get_page_obj(dict(contentful_id=content_id))

    def get_page(self, content_type, lang):
        return self._get_page_obj(dict(content_type=content_type, language=lang))

    def get_homepage(self, lang):
        return self.get_page('connectHomepage', lang)


class ContentfulEntry(models.Model):
    contentful_id = models.CharField(max_length=20, unique=True)
    content_type = models.CharField(max_length=20)
    language = models.CharField(max_length=5)
    last_modified = models.DateTimeField(default=now)
    url_base = models.CharField(max_length=255, blank=True)
    slug = models.CharField(max_length=255, blank=True)
    data_hash = models.CharField(max_length=64)
    data = JSONField()

    objects = ContentfulEntryManager()

    class Meta:
        unique_together = ('content_type', 'language')
