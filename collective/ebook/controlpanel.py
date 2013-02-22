# -*- coding: utf-8 -*-

from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.component import queryUtility

from plone.resource.interfaces import IResourceDirectory
from plone.registry.interfaces import IRegistry

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage

from zExceptions import Unauthorized, NotFound

from .interfaces import RESOURCE_PATH
from .interfaces import ISettings
from .vocabularies import Templates


def traverse(directory, path):
    try:
        for part in RESOURCE_PATH.split('/'):
            directory = directory[part]
    except NotFound:
        return

    return directory


class ControlPanel(object):
    template = ViewPageTemplateFile("controlpanel.pt")

    def __call__(self):
        persistent = queryUtility(IResourceDirectory, name="persistent")
        static = getUtility(IResourceDirectory, name="++ebook++templates")

        error = None

        try:
            settings = getUtility(IRegistry).forInterface(ISettings)
        except BaseException:
            settings = None

        if persistent is not None and self.request.method == 'POST':
            authenticator = getMultiAdapter(
                (self.context, self.request), name=u"authenticator"
            )

            if not authenticator.verify():
                raise Unauthorized

            # This is a no-op if the directory already exists.
            persistent.makeDirectory(RESOURCE_PATH)

            if self.request.form.get('copy'):
                for entry in static.listDirectory():
                    data = static.readFile(entry)

                    # For the persistent interface, entries must be
                    # byte strings.
                    entry = entry.encode('utf-8')

                    if entry in persistent:
                        continue

                    persistent.writeFile(RESOURCE_PATH + '/' + entry, data)

            if self.request.form.get('save'):
                if not self.request.form.get('html_to_pdf_executable'):
                    error = u'Påkrævede felter mangler.'
                else:
                    saved = False
                    for name, value in self.request.form.items():
                        decoded = value.decode('utf-8')
                        try:
                            if getattr(settings, name) != decoded:
                                setattr(settings, name, decoded)
                        except AttributeError:
                            pass
                        else:
                            saved = True

                    IStatusMessage(self.request).addStatusMessage(
                        u"Indstillinger gemt." if saved else
                        u"Ingen ændringer foretaget.", "info"
                    )

            if not error:
                url = self.request.getURL()
                return self.request.response.redirect(url)

        directory = traverse(persistent, RESOURCE_PATH)

        return self.template(
            error=error,
            directory=directory,
            settings=settings,
            templates=Templates(self.context),
        )
