from functools import partialmethod

from django.conf import settings
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

import contentful as api
from crum import get_current_request, set_current_request
from django.utils.functional import cached_property
from rich_text_renderer import RichTextRenderer
from rich_text_renderer.base_node_renderer import BaseNodeRenderer
from rich_text_renderer.block_renderers import BaseBlockRenderer
from rich_text_renderer.text_renderers import BaseInlineRenderer
from lib.l10n_utils import render_to_string, get_locale


# Bedrock to Contentful locale map
LOCALE_MAP = {
    'de': 'de-DE',
}
ASPECT_RATIOS = {
    '1:1': '1-1',
    '3:2': '3-2',
    '16:9': '16-9',
}
ASPECT_MULTIPLIER = {
    '1:1': 1,
    '3:2': 0.6666,
    '16:9': 0.5625
}
PRODUCT_THEMES = {
    'Firefox': 'family',
    'Firefox Browser': 'firefox',
    'Firefox Browser Beta': 'beta',
    'Firefox Browser Developer': 'developer',
    'Firefox Browser Nightly': 'nightly',
    'Firefox Browser Focus': 'focus',
    'Firefox Monitor': 'monitor',
    'Firefox Lockwise': 'lockwise',
    'Mozilla': 'mozilla',
    'Mozilla VPN': 'vpn',
    'Pocket': 'pocket',
}
WIDTHS = {
    'Extra Small': 'xs',
    'Small': 'sm',
    'Medium': 'md',
    'Large': 'lg',
    'Extra Large': 'xl',
    'Max': 'max',
}
LAYOUT_CLASS = {
    'layout2Cards': 'mzp-l-card-half',
    'layout3Cards': 'mzp-l-card-third',
    'layout4Cards': 'mzp-l-card-quarter',
    'layout5Cards': 'mzp-l-card-hero',
}
THEME_CLASS = {
    'Light': '',
    'Light (alternative)': 'mzp-t-background-alt',
    'Dark': 'mzp-t-dark',
    'Dark (alternative)': 'mzp-t-dark mzp-t-background-alt',
}
COLUMN_CLASS = {
    '1': '',
    '2': 'mzp-l-columns mzp-t-columns-two ',
    '3': 'mzp-l-columns mzp-t-columns-three',
    '4': 'mzp-l-columns mzp-t-columns-four',
}


def get_client(raw_mode=False):
    client = None
    if settings.CONTENTFUL_SPACE_ID:
        client = api.Client(
            settings.CONTENTFUL_SPACE_ID,
            settings.CONTENTFUL_SPACE_KEY,
            environment='V0',
            api_url=settings.CONTENTFUL_SPACE_API,
            raw_mode=raw_mode,
            content_type_cache=False,
        )

    return client


def contentful_locale(locale):
    """Returns the Contentful locale for the Bedrock locale"""
    if locale.startswith('es-'):
        return 'es'

    return LOCALE_MAP.get(locale, locale)


def _get_height(width, aspect):
    return round(width * ASPECT_MULTIPLIER.get(aspect, 0))


def _get_image_url(image, width):
    return 'https:' + image.url(
        w=width,
    )


def _get_card_image_url(image, width, aspect):
    return 'https:' + image.url(
        w=width,
        h=_get_height(width, aspect),
        fit='fill',
        f='faces',
    )


def _get_product_class(product):
    return f'mzp-t-product-{PRODUCT_THEMES.get(product, "")}'


def _get_layout_class(layout):
    return LAYOUT_CLASS.get(layout, '')


def _get_abbr_from_width(width):
    return WIDTHS.get(width, '')


def _get_aspect_ratio_class(aspect_ratio):
    return f'mzp-has-aspect-{ASPECT_RATIOS.get(aspect_ratio, "")}'


def _get_width_class(width):
    return f'mzp-t-content-{WIDTHS.get(width, "")}' if width else ''


def _get_theme_class(theme):
    return THEME_CLASS.get(theme, '')


def _get_youtube_id(youtube_url):
    url_data = urlparse(youtube_url)
    queries = parse_qs(url_data.query)
    youtube_id = queries["v"][0]
    return youtube_id


def _get_column_class(columns):
    return COLUMN_CLASS.get(columns, '')


def _make_logo(entry):
    fields = entry.fields()
    product = fields['product_icon']

    data = {
        'product_name': product,
        'product_icon': PRODUCT_THEMES.get(product, ''),
        'icon_size': WIDTHS.get(fields.get("icon_size"), '') if fields.get('icon_size') else 'md',
    }

    return render_to_string('includes/contentful/logo.html', data, get_current_request())


def _make_wordmark(entry):
    fields = entry.fields()
    product = fields['product_icon']

    data = {
        'product_name': product,
        'product_icon': PRODUCT_THEMES.get(product, ''),
        'icon_size': WIDTHS.get(fields.get("icon_size"), '') if fields.get('icon_size') else 'md',
    }

    return render_to_string('includes/contentful/wordmark.html', data, get_current_request())


def _make_cta_button(entry):
    fields = entry.fields()

    button_class = [
        'mzp-t-product',  # TODO, only add on Firefox themed pages
        'mzp-t-secondary' if fields.get('theme') == 'Secondary' else '',
        f'mzp-t-{WIDTHS.get(fields.get("size"), "")}' if fields.get('size') else '',
    ]

    data = {
        'action': fields.get('action'),
        'label': fields.get('label'),
        'button_class': ' '.join(button_class),
        # TODO
        'location': '',  # eg primary, secondary
        'cta_text': fields.get('label'),  # TODO needs to use English in all locales
    }
    return render_to_string('includes/contentful/cta.html', data, get_current_request())


def _make_plain_text(node):
    content = node['content']
    plain = ''

    for child_node in content:
        plain += child_node['value']

    # TODO
    # return unidecode(plain)
    return plain


def _only_child(node, nodeType):
    content = node['content']
    found = 0
    only = True
    for child_node in content:
        # if it's not the matching node type
        if child_node['nodeType'] != nodeType and found == 0:
            # and not an empty text node
            if child_node['nodeType'] == 'text' and child_node['value'] != '':
                # it's not the only child
                only = False
                break
        # if it's the second matching node type it's not the only child
        elif child_node['nodeType'] == nodeType:
            found += 1
            if found > 1:
                only = False
                break

    return only


class StrongRenderer(BaseInlineRenderer):
    @property
    def _render_tag(self):
        return 'strong'


class EmphasisRenderer(BaseInlineRenderer):
    @property
    def _render_tag(self):
        return 'em'


class LinkRenderer(BaseBlockRenderer):
    def render(self, node):
        url = urlparse(node["data"]["uri"])
        request = get_current_request()
        ref = ''
        rel = ''
        data_cta = ''

        # add referral info to links to other mozilla properties
        if 'mozilla.org' in url.netloc and url.netloc != 'www.mozilla.org':
            # don't add if there's already utms
            if 'utm_' not in url.query:
                params = {
                    'utm_source': 'www.mozilla.org',
                    'utm_medium': 'referral',
                    'utm_campaign': request.page_info['utm_campaign'],
                }
                add = '?' if url.query == '' else '&'
                ref = add + urlencode(params)

        # TODO, should this be based on the current server (ie dev, stage)?
        # add attributes for external links
        if url.netloc != 'www.mozilla.org':
            # add security measures
            rel = ' rel="external noopener"'
            # add analytics
            cta_text = _make_plain_text(node)
            data_cta = f' data-cta-type="link" data-cta-text="{cta_text}"'

        return '<a href="{0}{1}"{2}{3}>{4}</a>'.format(
            urlunparse(url), ref, data_cta, rel, self._render_content(node)
        )


def _render_list(tag, content):
    return f"<{tag} class='mzp-u-list-styled'>{content}</{tag}>"


class UlRenderer(BaseBlockRenderer):
    def render(self, node):
        return _render_list('ul', self._render_content(node))


class OlRenderer(BaseBlockRenderer):
    def render(self, node):
        return _render_list('ol', self._render_content(node))


class LiRenderer(BaseBlockRenderer):
    def render(self, node):
        if _only_child(node, 'text'):
            # The outter text node gets rendered as a paragraph... don't do that if there's only one p in the li
            return f"<li>{self._render_content(node['content'][0])}</li>"
        else:
            return f"<li>{self._render_content(node)}</li>"


class PRenderer(BaseBlockRenderer):
    def render(self, node):
        # contains only one node which is a link
        if _only_child(node, 'hyperlink'):
            # add cta-link class
            # TODO, class shoudl be added to <a>?
            return f'<p class="mzp-c-cta-link">{self._render_content(node)}</p>'
        # contains only an empty text node
        elif len(node['content']) == 1 and node['content'][0]['nodeType'] == 'text' and node['content'][0]['value'] == '':
            # just say no to empty p tags
            return ''
        else:
            return f"<p>{self._render_content(node)}</p>"


class InlineEntryRenderer(BaseNodeRenderer):
    def render(self, node):
        entry_id = node['data']['target']['sys']['id']
        entry = ContentfulPage.client.entry(entry_id)
        content_type = entry.sys['content_type'].id

        if content_type == 'componentLogo':
            return _make_logo(entry)
        elif content_type == 'componentWordmark':
            return _make_wordmark(entry)
        elif content_type == 'componentCtaButton':
            return _make_cta_button(entry)
        else:
            return content_type


class AssetBlockRenderer(BaseBlockRenderer):
    IMAGE_HTML = '<img src="{src}" srcset="{src_highres} 1.5x" alt="{alt}" />'

    def render(self, node):
        asset_id = node['data']['target']['sys']['id']
        asset = ContentfulPage.client.asset(asset_id)
        return self.IMAGE_HTML.format(
            src=_get_image_url(asset, 688),
            src_highres=_get_image_url(asset, 1376),
            alt=asset.title,
        )


class ContentfulPage:
    # TODO: List: stop list items from being wrapped in paragraph tags
    # TODO: Error/ Warn / Transform links to allizom
    client = get_client()
    _renderer = RichTextRenderer({
        'hyperlink': LinkRenderer,
        'bold': StrongRenderer,
        'italic': EmphasisRenderer,
        'unordered-list': UlRenderer,
        'ordered-list': OlRenderer,
        'list-item': LiRenderer,
        'paragraph': PRenderer,
        'embedded-entry-inline': InlineEntryRenderer,
        'embedded-asset-block': AssetBlockRenderer,
    })
    SPLIT_LAYOUT_CLASS = {
        'Even': '',
        'Narrow': 'mzp-l-split-body-narrow',
        'Wide': 'mzp-l-split-body-wide',
    }

    SPLIT_MEDIA_WIDTH_CLASS = {
        'Fill available width': '',
        'Fill available height': 'mzp-l-split-media-constrain-height',
        'Overflow container': 'mzp-l-split-media-overflow',
    }

    SPLIT_V_ALIGN_CLASS = {
        'Top': 'mzp-l-split-v-start',
        'Center': 'mzp-l-split-v-center',
        'Bottom': 'mzp-l-split-v-end',
    }

    SPLIT_H_ALIGN_CLASS = {
        'Left': 'mzp-l-split-h-start',
        'Center': 'mzp-l-split-h-center',
        'Right': 'mzp-l-split-h-end',
    }

    SPLIT_POP_CLASS = {
        'None': '',
        'Both': 'mzp-l-split-pop',
        'Top': 'mzp-l-split-pop-top',
        'Bottom': 'mzp-l-split-pop-bottom',
    }
    CONTENT_TYPE_MAP = {
        'componentHero': {
            'proc': 'get_hero_data',
            'css': 'c-hero',
        },
        'componentSectionHeading': {
            'proc': 'get_section_data',
            'css': 'c-section-heading',
        },
        'componentSplitBlock': {
            'proc': 'get_split_data',
            'css': 'c-split',
        },
        'componentCallout': {
            'proc': 'get_callout_data',
            'css': 'c-call-out',
        },
        'layout2Cards': {
            'proc': 'get_card_layout_data',
            'css': 't-card-layout',
            'js': 'c-card'
        },
        'layout3Cards': {
            'proc': 'get_card_layout_data',
            'css': 't-card-layout',
            'js': 'c-card'
        },
        'layout4Cards': {
            'proc': 'get_card_layout_data',
            'css': 't-card-layout',
            'js': 'c-card'
        },
        'layout5Cards': {
            'proc': 'get_card_layout_data',
            'css': 't-card-layout',
            'js': 'c-card'
        },
        'layoutPictoBlocks': {
            'proc': 'get_picto_layout_data',
            'css': ('c-picto', 't-multi-column'),
        },
        'textOneColumn': {
            'proc': 'get_text_column_data_1',
            'css': 't-multi-column',
        },
        'textTwoColumns': {
            'proc': 'get_text_column_data_2',
            'css': 't-multi-column',
        },
        'textThreeColumns': {
            'proc': 'get_text_column_data_3',
            'css': 't-multi-column',
        },
        'textFourColumns': {
            'proc': 'get_text_column_data_4',
            'css': 't-multi-column',
        },
    }

    def __init__(self, request, page_id):
        set_current_request(request)
        self.request = request
        self.page_id = page_id
        self.locale = get_locale(request)

    @cached_property
    def page(self):
        return self.client.entry(self.page_id, {
            'include': 10,
        })

    def render_rich_text(self, node):
        return self._renderer.render(node) if node else ''

    def get_info_data(self, entry_obj):
        # TODO, need to enable connectors
        fields = entry_obj.fields()
        folder = fields.get('folder', '')
        in_firefox = 'firefox-' if 'firefox' in folder else ''
        slug = fields.get('slug', 'home')
        campaign = f'{in_firefox}{slug}'
        page_type = entry_obj.content_type.id
        if page_type == 'pageHome':
            lang = fields['name']
        else:
            lang = entry_obj.sys['locale']

        data = {
            'title': fields.get('preview_title', ''),
            'blurb': fields.get('preview_blurb', ''),
            'slug': slug,
            'lang': lang,
            'theme': 'firefox' if 'firefox' in folder else 'mozilla',
            # eg www.mozilla.org-firefox-accounts or www.mozilla.org-firefox-sync
            'utm_source': f'www.mozilla.org-{campaign}',
            'utm_campaign': campaign,  # eg firefox-sync
        }

        if 'preview_image' in fields:
            # TODO request proper size image
            preview_image_url = fields['preview_image'].fields().get('file').get('url')
            data['image'] = 'https:' + preview_image_url

        return data

    def get_entry_by_id(self, entry_id):
        return self.client.entry(entry_id, {'locale': self.locale})

    def get_content(self):
        # check if it is a page or a connector
        entry_type = self.page.content_type.id
        if entry_type.startswith('page'):
            entry_obj = self.page
        elif entry_type == 'connectHomepage':
            entry_obj = self.page.fields()['entry']
        else:
            raise ValueError(f'{entry_type} is not a recognized page type')

        self.request.page_info = self.get_info_data(entry_obj)
        page_type = entry_obj.content_type.id
        page_css = set()
        page_js = set()
        fields = entry_obj.fields()
        content = None
        entries = []

        def proc(item):
            content_type = item.sys.get('content_type').id
            ctype_info = self.CONTENT_TYPE_MAP.get(content_type)
            if ctype_info:
                processor = getattr(self, ctype_info['proc'])
                entries.append(processor(item))
                css = ctype_info.get('css')
                if css:
                    if isinstance(css, str):
                        css = (css,)

                    page_css.update(css)

                js = ctype_info.get('js')
                if js:
                    if isinstance(js, str):
                        js = (js,)

                    page_js.update(js)

        if page_type == 'pageGeneral':
            # look through all entries and find content ones
            for key, value in fields.items():
                if key == 'component_hero':
                    proc(value)
                elif key == 'body':
                    entries.append(self.get_text_data(value))
                elif key == 'component_callout':
                    proc(value)
        elif page_type == 'pageVersatile':
            content = fields.get('content')
        elif page_type == 'pageHome':
            content = fields.get('content')

        if content:
            # get components from content
            for item in content:
                proc(item)

        return {
            'page_type': page_type,
            'page_css': list(page_css),
            'page_js': list(page_js),
            'info': self.request.page_info,
            'entries': entries,
        }

    def get_text_data(self, value):
        data = {
            'component': 'text',
            'body': self.render_rich_text(value),
            'width_class': _get_width_class('Medium')  # TODO
        }

        return data

    def get_hero_data(self, entry_obj):
        fields = entry_obj.fields()

        hero_image_url = _get_image_url(fields['image'], 800)
        hero_reverse = fields.get('image_side')
        hero_body = self.render_rich_text(fields.get('body'))

        data = {
            'component': 'hero',
            'theme_class': _get_theme_class(fields.get('theme')),
            'product_class': _get_product_class(fields.get('product_icon')) if fields.get('product_icon') and fields.get('product_icon') != 'None' else '',
            'title': fields.get('heading'),
            'tagline': fields.get('tagline'),
            'body': hero_body,
            'image': hero_image_url,
            'image_class': 'mzp-l-reverse' if hero_reverse == 'Left' else '',
            'include_cta': True if fields.get('cta') else False,
            'cta': _make_cta_button(fields.get('cta')) if fields.get('cta') else '',
        }

        return data

    def get_section_data(self, entry_obj):
        fields = entry_obj.fields()

        data = {
            'component': 'sectionHeading',
            'heading': fields.get('heading'),
        }

        return data

    def get_split_data(self, entry_obj):
        fields = entry_obj.fields()

        def get_split_class():
            block_classes = [
                'mzp-l-split-reversed' if fields.get('image_side') == 'Left' else '',
                self.SPLIT_LAYOUT_CLASS.get(fields.get('body_width'), ''),
                self.SPLIT_POP_CLASS.get(fields.get('image_pop'), ''),
            ]
            return ' '.join(block_classes)

        def get_body_class():
            body_classes = [
                self.SPLIT_V_ALIGN_CLASS.get(fields.get('body_vertical_alignment'), ''),
                self.SPLIT_H_ALIGN_CLASS.get(fields.get('body_horizontal_alignment'), ''),
            ]
            return ' '.join(body_classes)

        def get_media_class():
            media_classes = [
                self.SPLIT_MEDIA_WIDTH_CLASS.get(fields.get('image_width'), ''),
                self.SPLIT_V_ALIGN_CLASS.get(fields.get('image_vertical_alignment'), ''),
                self.SPLIT_H_ALIGN_CLASS.get(fields.get('image_horizontal_alignment'), ''),
            ]
            return ' '.join(media_classes)

        def get_mobile_class():
            mobile_display = fields.get('mobile_display')
            if not mobile_display:
                return ''

            mobile_classes = [
                'mzp-l-split-center-on-sm-md' if 'Center content' in mobile_display else '',
                'mzp-l-split-hide-media-on-sm-md' if 'Hide image' in mobile_display else '',
            ]
            return ' '.join(mobile_classes)

        split_image_url = _get_image_url(fields['image'], 800)

        data = {
            'component': 'split',
            'block_class': get_split_class(),
            'theme_class': _get_theme_class(fields.get('theme')),
            'body_class': get_body_class(),
            'body': self.render_rich_text(fields.get('body')),
            'media_class': get_media_class(),
            'image': split_image_url,
            'mobile_class': get_mobile_class(),
        }

        return data

    def get_callout_data(self, entry_obj):
        fields = entry_obj.fields()

        data = {
            'component': 'callout',
            'theme_class': _get_theme_class(fields.get('theme')),
            'product_class': _get_product_class(fields.get('product_icon')) if fields.get('product_icon') else '',
            'title': fields.get('heading'),
            'body': self.render_rich_text(fields.get('body')) if fields.get('body') else '',
            'cta': _make_cta_button(fields.get('cta')),
        }

        return data

    def get_card_data(self, entry_obj, aspect_ratio):
        # need a fallback aspect ratio
        aspect_ratio = aspect_ratio or '16:9'
        fields = entry_obj.fields()
        card_body = self.render_rich_text(fields.get('body')) if fields.get('body') else ''
        image_url = highres_image_url = ''

        if 'image' in fields:
            card_image = fields.get('image')
            # TODO smaller image files when layout allows it
            highres_image_url = _get_card_image_url(card_image, 800, aspect_ratio)
            image_url = _get_card_image_url(card_image, 800, aspect_ratio)

        if 'you_tube' in fields:
            # TODO: add youtube JS to page_js
            youtube_id = _get_youtube_id(fields.get('you_tube'))
        else:
            youtube_id = ''

        data = {
                'component': 'card',
                'heading': fields.get('heading'),
                'tag': fields.get('tag'),
                'link': fields.get('link'),
                'body': card_body,
                'aspect_ratio': _get_aspect_ratio_class(aspect_ratio) if image_url != '' else '',
                'highres_image_url': highres_image_url,
                'image_url': image_url,
                'youtube_id': youtube_id,
            }

        return data

    def get_large_card_data(self, entry_obj, card_obj):
        fields = entry_obj.fields()

        # get card data
        card_data = self.get_card_data(card_obj, "16:9")

        # large card data
        large_card_image = fields.get('image')
        if large_card_image:
            highres_image_url = _get_card_image_url(large_card_image, 1860, "16:9")
            image_url = _get_card_image_url(large_card_image, 1860, "16:9")

            # over-write with large values
            card_data['component'] = 'large_card'
            card_data['highres_image_url'] = highres_image_url
            card_data['image_url'] = image_url

        return card_data

    def get_card_layout_data(self, entry_obj):
        fields = entry_obj.fields()
        aspect_ratio = fields.get('aspect_ratio')
        layout = entry_obj.sys.get('content_type').id

        data = {
            'component': 'cardLayout',
            'layout_class': _get_layout_class(layout),
            'aspect_ratio': aspect_ratio,
            'cards': [],
        }

        follows_large_card = False
        if layout == 'layout5Cards':
            card_layout_obj = fields.get('large_card')
            card_obj = fields.get('large_card').fields().get('card')
            large_card_data = self.get_large_card_data(card_layout_obj, card_obj)

            data.get('cards').append(large_card_data)
            follows_large_card = True

        cards = fields.get('content')
        for card in cards:
            if follows_large_card:
                this_aspect = '1:1'
                follows_large_card = False
            else:
                this_aspect = aspect_ratio
            card_data = self.get_card_data(card, this_aspect)
            data.get('cards').append(card_data)

        return data

    def get_picto_data(self, picto_obj, image_width):

        fields = picto_obj.fields()
        body = self.render_rich_text(fields.get('body')) if fields.get('body') else False

        if 'icon' in fields:
            picto_image = fields.get('icon')
            image_url = _get_image_url(picto_image, image_width)
        else:
            image_url = ''  # TODO: this should cause an error, the macro requires an image

        return {
            'component': 'picto',
            'heading': fields.get('heading'),
            'body': body,
            'image_url': image_url,
        }

    def get_picto_layout_data(self, entry):
        PICTO_ICON_SIZE = {
            'Small': 32,
            'Medium': 48,
            'Large': 64,
            'Extra Large': 96,
            'Extra Extra Large': 192,
        }
        fields = entry.fields()
        # layout = entry.sys.get('content_type').id

        def get_layout_class():
            column_class = _get_column_class(str(fields.get('blocks_per_row')))
            layout_classes = [
                _get_width_class(fields.get('width')),
                column_class or '3',
                'mzp-t-picto-side' if fields.get('icon_position') == 'Side' else '',
                'mzp-t-picto-center' if fields.get('block_alignment') == 'Center' else '',
                _get_theme_class(fields.get('theme')),
            ]

            return ' '.join(layout_classes)

        image_width = PICTO_ICON_SIZE.get(fields.get('icon_size')) if fields.get('icon_size') else PICTO_ICON_SIZE.get("Large")

        data = {
            'component': 'pictoLayout',
            'layout_class': get_layout_class(),
            'heading_level': fields.get('heading_level')[1:] if fields.get('heading_level') else 3,
            'image_width': image_width,
            'pictos': [],
        }

        pictos = fields.get('content')
        for picto_obj in pictos:
            picto_data = self.get_picto_data(picto_obj, image_width)
            data.get('pictos').append(picto_data)

        return data

    def get_text_column_data(self, cols, entry_obj):
        fields = entry_obj.fields()

        def get_content_class():
            content_classes = [
                _get_width_class(fields.get('width')),
                _get_column_class(str(cols)),
                _get_theme_class(fields.get('theme')),
                'mzp-u-center' if fields.get('block_alignment') == 'Center' else '',
            ]

            return ' '.join(content_classes)

        data = {
            'component': 'textColumns',
            'layout_class': get_content_class(),
            'content': [self.render_rich_text(fields.get('body_column_one'))],
        }

        if cols > 1:
            data['content'].append(self.render_rich_text(fields.get('body_column_two')))
        if cols > 2:
            data['content'].append(self.render_rich_text(fields.get('body_column_three')))
        if cols > 3:
            data['content'].append(self.render_rich_text(fields.get('body_column_four')))

        return data

    get_text_column_data_1 = partialmethod(get_text_column_data, 1)
    get_text_column_data_2 = partialmethod(get_text_column_data, 2)
    get_text_column_data_3 = partialmethod(get_text_column_data, 3)
    get_text_column_data_4 = partialmethod(get_text_column_data, 4)


# TODO make optional fields optional
