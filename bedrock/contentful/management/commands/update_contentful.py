import json
from hashlib import sha256

from django.conf import settings
from django.core.management.base import BaseCommand

from bedrock.contentful.api import get_client
from bedrock.contentful.models import ContentfulEntry


def data_hash(data):
    str_data = json.dumps(data, sort_keys=True)
    return sha256(str_data.encode('utf8')).hexdigest()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('-q', '--quiet', action='store_true', dest='quiet', default=False,
                            help='If no error occurs, swallow all output.'),
        parser.add_argument('-f', '--force', action='store_true', dest='force', default=False,
                            help='Load the data even if nothing new from Contentful.'),

    def log(self, msg):
        if not self.quiet:
            print(msg)

    def handle(self, *args, **options):
        self.quiet = options['quiet']
        self.force = options['force']
        self.log('Updating Contentful Data')
        added, updated = self.refresh()
        self.log(f'Done. Added: {added}. Updated: {updated}')

    def refresh(self):
        client = get_client()
        raw_client = get_client(True)
        updated_count = 0
        added_count = 0
        content_ids = []
        for ctype in settings.CONTENTFUL_CONTENT_TYPES:
            for entry in client.entries({'content_type': ctype, 'include': 0}).items:
                content_ids.append((ctype, entry.sys['id']))

        for ctype, page_id in content_ids:
            resp = raw_client.entries({'sys.id': page_id, 'include': 10})
            resp.raise_for_status()
            page = resp.json()
            hash = data_hash(page)
            if ctype == 'connectHomepage':
                language = page['items'][0]['fields']['name']
            else:
                language = page['items'][0]['sys']['locale']

            try:
                obj = ContentfulEntry.objects.get(contentful_id=page_id)
            except ContentfulEntry.DoesNotExist:
                ContentfulEntry.objects.create(
                    contentful_id=page_id,
                    content_type=ctype,
                    language=language,
                    data_hash=hash,
                    data=page,
                )
                added_count += 1
            else:
                if self.force or hash != obj.data_hash:
                    obj.language = language
                    obj.data_hash = hash
                    obj.data = page
                    obj.save()
                    updated_count += 1

        return added_count, updated_count
