import os
import re
import cgi
import base64
import imghdr
import urllib
import logging
import operator
import itertools
import htmlentitydefs

try:
    from simplejson import dumps
except ImportError:
    from json import dumps

from subprocess import Popen, PIPE

from BeautifulSoup import BeautifulSoup
from DateTime import DateTime
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.component import queryUtility

from zope.pagetemplate.pagetemplatefile import PageTemplate
from zope.pagetemplate.pagetemplatefile import PageTemplateFile

from AccessControl import getSecurityManager
from Acquisition import aq_base, aq_inner
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.PageTemplates.Expressions import createTrustedZopeEngine
from Products.CMFCore.utils import getToolByName
from plone.resource.interfaces import IResourceDirectory
from plone.registry.interfaces import IRegistry
from plone.i18n.normalizer.interfaces import IURLNormalizer
from plone.app.layout.navigation.defaultpage import getDefaultPage
from plone.app.layout.navigation.defaultpage import isDefaultPage

from ZODB.utils import u64
from zExceptions import BadRequest
from zExceptions import Unauthorized
from zExceptions import NotFound
from zExceptions import InternalError

from .interfaces import RESOURCE_PATH
from .interfaces import ISettings

logger = logging.getLogger("collective.ebook")
shy = unichr(htmlentitydefs.name2codepoint['shy'])
re_shy = re.compile(r'(?<=[\w0-9])([/\-.&])')
re_level = re.compile(r'level-(\d+)')


def image_encode(data, mimetype=None, filename=""):
    if not data:
        return

    if mimetype is None:
        mimetype = 'image/%s' % imghdr.what(filename, data)

    return "data:%s;base64,%s" % (mimetype, base64.b64encode(data))


class PathSort(object):
    def __init__(self, paths):
        self.length = len(paths)
        self.range = max(path.count('/') for path in paths) + 1
        self.index = dict(
            (path, n) for (n, path) in enumerate(paths)
        ).__getitem__
        self.subpaths = dict(
            (path, ["/".join(parts[:n]) for n in xrange(1, len(parts) + 1)])
            for (path, parts) in [(path, path.split('/')) for path in paths]
        )

    def get_key(self, path):
        subpaths = self.subpaths[path]

        v = 0
        for index, subpath in enumerate(subpaths):
            try:
                i = self.index(subpath) + 1
            except KeyError:
                i = 0

            v += i * self.length ** (self.range - index)

        return v

    def get_level(self, path):
        subpaths = self.subpaths[path]
        j = 0
        for i, subpath in enumerate(reversed(subpaths)):
            try:
                self.index(subpath)
            except KeyError:
                pass
            else:
                j = i

        return j + 1


FALLBACK_IMAGE = image_encode(
    open(os.path.join(os.path.dirname(__file__), 'static', 'missing.jpg'),
         'rb').read(),
)


class LoadBase64(object):
    def __init__(self, directory):
        self.directory = directory

    def __call__(self, name):
        try:
            source = self.directory[name]
        except NotFound:
            return FALLBACK_IMAGE

        try:
            data = open(source.path, 'rb').read()
        except AttributeError:
            data = str(source)

        return image_encode(data)


class FormViewlet(object):
    available = False
    template = ViewPageTemplateFile("form.pt")

    def update(self):
        try:
            settings = getUtility(IRegistry).forInterface(ISettings)
            if(settings.allow_globally):
                self.available = True
                return
        except BaseException:
            settings = None
        field = self.context.getField('enablePDF')
        if field is not None:
            self.available = field.get(self.context)

    def render(self):
        if self.available:
            folder = aq_inner(self.context)
            if not getattr(aq_base(folder), 'isPrincipiaFolderish', False):
                folder = folder.aq_parent

            options = {
                'unique_id': self.getUniqueId(),
                'uid': folder.UID(),
                'folder': folder,
            }

            return self.template(**options)

        return u""

    def getUniqueId(self):
        return u64(self.context._p_oid)

    def isManager(self):
        user = getSecurityManager().getUser()
        return 'Manager' in user.getRolesInContext(self.context)


class HelperView(object):
    template = ViewPageTemplateFile("item.pt")

    engine = createTrustedZopeEngine()
    namespace = engine.getBaseNames()

    def isEnabled(self):
        layout = self.context.getDefaultLayout()
        if not self.request.getURL().endswith('/' + layout):
            return False

        settings = getUtility(IRegistry).forInterface(ISettings)
        if(settings.allow_globally):
            return True
        field = self.context.getField('enablePDF')
        if field is not None:
            return field.get(self.context)

        return False

    def publish(self, item, level):
        default_page = getDefaultPage(item)
        if default_page is not None:
            try:
                item = item[default_page]
            except KeyError:
                pass

        title = '<h%d>%s</h%d>' % (
            level, cgi.escape(item.Title()), level
        )

        if default_page is not None:
            level += 1

        try:
            text = item.getText()
        except AttributeError:
            if(item.portal_type == 'Image'):
                text = '%s\n<img src="%s"/>' % (title, item.absolute_url_path())
            else:
                return '<div class="section" id="%s">%s</div><p>%s content can not be embedded into the PDF.</p>' % (item.UID(), title, item.portal_type)

        soup = BeautifulSoup(text)

        # Inline images.
        for link in soup.findAll("img"):
            self.inlineImage(item, link)

        # Resolve relative links.
        for link in soup.findAll("a"):
            self.resolveRelativeLink(item, link)

        headings = reduce(
            operator.add,
            itertools.imap(soup.findAll, ("h1", "h2", "h3", "h4", "h5"))
        )

        if headings:
            levels = [(int(heading.name[1]), heading) for heading in headings]
            largest = min(l[0] for l in levels)
            difference = largest - level - 1

            # Demote headings by the difference.
            if difference:
                for l, h in levels:
                    h.name = "h%d" % (l - difference)

        return '<div class="section" id="%s">%s</div>' % (item.UID(),"\n".join((title, str(soup))))

    def process(self, items):
        text = "\n".join(self.publish(item, level) for (item, level) in items)

        soup = BeautifulSoup(text)
        normalizer = getUtility(IURLNormalizer).normalize

        stack = [{'children': [], 'level': 0}]

        headings = soup.findAll(('h1', 'h2', 'h3', 'h4', 'h5', 'h6'))

        for index, heading in enumerate(headings):
            level = int(heading.name[1])

            hid = 'section-' + normalizer(heading.string) + '-%d' % (index + 1)

            title = u''
            for string in heading.recursiveChildGenerator():
                if isinstance(string, unicode):
                    title += string.lstrip('123456789. ').strip()

            # Remove trivial headings
            if not title:
                heading.extract()
                continue

            entry = {
                'title': title,
                'id': hid,
                'children': [],
                'level': level,
            }

            i = 0
            while level <= stack[-1]['level']:
                stack.pop()
                i += 1

            stack[-1]['children'].append(entry)
            stack.append(entry)

            heading['id'] = hid

            if level == 1:
                heading.name = 'h2'
                heading['class'] = 'documentFirstHeading'

        # Make sure we start with a heading (default to 'own').
        for child in soup.recursiveChildGenerator():
            if isinstance(child, unicode):
                if child.strip('\n '):
                    hid = 'section-0'
                    title = self.context.Title().decode('utf-8')
                    soup.insert(0, '<h2 id="%s">%s</h2>' % (hid, title))
                    # stack[0]['children'].insert(
                    #    0, {'title': title,
                    #        'id': hid,
                    #        'children': [],
                    #        'level': 2,
                    #        })
                    break
            elif child.name.startswith('h'):
                break

        while len(stack[0]['children']) == 1:
            stack[0] = stack[0]['children'].pop()

        return soup, stack[0]['children']

    def getChildrenAsJson(self, key=None, select=True):
        self.request.response.setHeader('Content-Type', 'application/json')

        catalog = getToolByName(self.context, 'portal_catalog')
        brains = catalog.searchResults(UID=key)

        if not brains:
            raise BadRequest("Object not found with UID: %r." % key)

        path = brains[0].getPath()

        results = catalog.searchResults(
            path={
                'query': path,
                'depth': 1
            },
            allowedRolesAndUsers='Anonymous',
            allowPDF=True,
            is_default_page=False,
            sort_on='getObjPositionInParent'
        )

        uid = self.context.UID()

        return dumps([
            {"key": brain.UID,
             "title": brain.Title,
             "isLazy": brain.is_folderish,
             "isFolder": brain.is_folderish,
             "select": select}
            for brain in results if brain.UID != uid
        ])

    def setHeader(self, name, value):
        self.request.response.setHeader(name, value)

    def render(self, soup, headings, pub_date, mod_date):
        try:
            settings = getUtility(IRegistry).forInterface(ISettings)
        except BaseException:
            settings = None

        # XXX: This seems very complicated and brittle!
        persistent = queryUtility(IResourceDirectory, name="persistent")
        if persistent is not None:
            try:
                templates = persistent[RESOURCE_PATH]
                source = templates[settings.template.decode('utf-8')]
            except NotFound:
                try:
                    name = "++%s++%s" % tuple(RESOURCE_PATH.split('/')[:2])
                    templates = getUtility(IResourceDirectory, name=name)
                    source = templates[settings.template]
                except NotFound:
                    raise InternalError(
                        "Template not found: %r." % settings.template
                    )


        try:
            body = source.lastModifiedTimestamp
        except AttributeError:
            body = str(source)

        cache_key = hash((source, body))
        template, cached_key = getattr(
            self.context, "_v_render_template", None
        ) or (None, cache_key)

        if template is None or cached_key != cache_key:
            try:
                path = source.path
            except AttributeError:
                template = PageTemplate()
                template.pt_edit(str(source), 'text/xml')
            else:
                template = PageTemplateFile(path)

            logger.info("compiling template %r (with class %r)" % (
                settings.template, template.__class__.__name__,
            ))

            # Always use the Zope 2 expression engine.
            template.pt_getEngine = lambda: self.engine

            # Pass options directly into the template namespace.
            template.pt_getContext = lambda args=(), options=None, **_: options

            # We need to cook the template again to make sure the
            # above settings are applied (double work!)
            template._cook()

            # Cache template on context.
            self.context._v_render_template = (template, cache_key)

        namespace = dict(
            context=aq_inner(self.context),
            request=self.request,
            macros=template.macros,
            soup=soup,
            headings=headings,
            inline=LoadBase64(templates),
            publication_date=pub_date,
            modification_date=mod_date,
        )

        namespace.update(self.namespace)
        html = template(**namespace)

        soup = BeautifulSoup(html)
        portal = self.context.portal_url.getPortalObject()
        portal_url = portal.absolute_url()

        # Write out external links.
        for link in soup.findAll("a"):
            self.transformLink(portal_url, link)

        return unicode(soup)

    
    def resolveuid(self, url):
        reference_tool = getToolByName(self, 'reference_catalog')
        m = re.search('resolveuid/([^/]+)(/.*)?', url)
        
        obj = reference_tool.lookupObject(m.groups()[0])
        if(obj):
            return '%s%s' % (obj.absolute_url(), m.groups()[1] or '')
        else:
            return url
    
    def inlineImage(self, context, image):
        url = image.get('src').encode('utf-8')
        if(url.startswith('resolveuid')):
            url = self.resolveuid(url)
        if(url.startswith(self.context.portal_url())):
            url = url[len(self.context.portal_url()):]
            url = url.lstrip('/')
        if '://' in url or url.startswith('data:'):
            return

        try:
            obj = context.restrictedTraverse(urllib.unquote(url))
            data = getattr(obj, "data", FALLBACK_IMAGE)
        except AttributeError:
            # the image might be a thumbnail
            img, kind = url.rsplit('/', 1)
            obj = context.restrictedTraverse(urllib.unquote(img))
            data = getattr(obj.getField('image').getScale(obj, kind.replace('image_', '')), "data", FALLBACK_IMAGE)
        except NotFound:
            image.extract()
            return

        encoded = image_encode(data)

        image['src'] = encoded

    def resolveRelativeLink(self, context, link):
        url = link.get('href', '')

        if not url.strip():
            return
        
        if(url.startswith('resolveuid')):
            url = self.resolveuid(url)
        if(url.startswith(self.context.absolute_url())):
            url = url[len(self.context.absolute_url()):]
            url = url.lstrip('/')
        if url.startswith('#'):
            return
        if url.startswith('mailto:'):
            return
        if url.startswith('\\\\'):
            return

        if '://' in url and url.index('://') <= 5:
            return

        if url.startswith('/'):
            context = self.context.portal_url.getPortalObject()
            url = url.lstrip('/')

        url = url.encode('utf-8')

        try:
            obj = context.restrictedTraverse(urllib.unquote(url))
        except NotFound:
            obj = context
        except Exception:
            logger.warn('error resolving url: %s' % url)
            return
        else:
            parent = obj.aq_parent
            if isDefaultPage(parent, obj):
                obj = parent

        link['href'] = '#%s' % obj.UID()

    def transformLink(self, portal_url, link):
        url = link.get('href', '')

        if not url.strip():
            return

        if url.startswith('#'):
            return

        if not url.startswith('http'):
            return

        if link.string is not None:
            s = link.string.strip(' .\n')
            if not s:
                link.extract()
                return
            link.string = s
        else:
            s = u""
            for child in tuple(link):
                if isinstance(child, unicode):
                    child.replaceWith(child.strip(' .\n'))
                    s += child

        if url.replace(u'http://', u'') in s.replace(u'http://', u''):
            return

        # Insert literal URL after link
        parent = link.parent
        index = tuple(parent).index(link)

        # URL-decode
        url = urllib.unquote(url)

        # Add shy hyphenation to avoid overflow.
        url = re_shy.sub(u'\\1' + shy, url)

        # CGI-Escape
        url = cgi.escape(url)

        parent.insert(index + 1, ' <span>(%s)</span>' % url)

    def submit(self, html=False, token=None, selNodes=None):
        authenticator = getMultiAdapter(
            (self.context, self.request), name=u"authenticator"
        )

        if not authenticator.verify():
            raise Unauthorized

        items, pub_date, mod_date = self.query(selNodes)

        if(self.context.getDefaultPage()):
            items.insert(0, (getattr(self.context, self.context.getDefaultPage()), 1))

        try:
            settings = getUtility(IRegistry).forInterface(ISettings)
        except BaseException:
            raise BadRequest("Settings not available.")

        soup, headings = self.process(items)
        data = self.render(soup, headings, pub_date, mod_date)
        data = data.replace('&nbsp;', '&#xA0;')

        if not html:
            name = self.context.portal_url.getPortalObject().Title().lower()
            self.setHeader('Content-Type', 'application/pdf')
            self.setHeader('Content-Disposition', 'attachment; filename=%s.pdf' % name)

            args = settings.html_to_pdf_executable.split(' ')

            if settings.ssh_host:
                args = [
                    'ssh',
                    '-o', 'ConnectTimeout=3',
                    '-o', 'BatchMode=yes',
                    '-o', 'StrictHostKeyChecking=no',
                    '-C', settings.ssh_host] + args

            p = Popen(args, stdin=PIPE, stdout=PIPE)

            if isinstance(data, unicode):
                data = data.encode('utf-8')

            p.stdin.write(data)
            p.stdin.close()

            data = p.stdout.read()

        # Set the download token, prompting Javascript to reset the
        # user interface.
        self.request.response.setCookie('ebook-download', token, quoted=False)

        return data

    def query(self, selNodes):
        brains = self.context.portal_catalog(UID=selNodes)
        paths = [brain.getPath() for brain in brains]

        # First, find all the selected nodes and their subtrees.
        brains = self.context.portal_catalog(
            path={'query': paths, 'depth': -1},
            allowedRolesAndUsers='Anonymous',
            allowPDF=True,
            is_default_page=False,
            sort_on='getObjPositionInParent',
        )

        # Retrieve all results.
        brains = list(brains)
        if not brains:
            today = DateTime()
            return (), today, today

        paths = [brain.getPath() for brain in brains]

        # Do a second sorting on subpath.
        sorter = PathSort(paths)
        brains.sort(key=lambda brain: sorter.get_key(brain.getPath()))

        # Resolve brains to acquisition-wrapped objects, and provide
        # path level relative to the originally selected tree nodes.
        items = [
            (brain.getObject(), sorter.get_level(brain.getPath()))
            for brain in brains
        ]

        return (
            items,
            max(brain.effective for brain in brains),
            max(brain.modified for brain in brains)
        )
