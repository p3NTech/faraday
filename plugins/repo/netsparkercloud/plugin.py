#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import with_statement
from plugins import core
from model import api
import re
import os
import sys
import socket
import urllib

try:
    import xml.etree.cElementTree as ET
    import xml.etree.ElementTree as ET_ORIG
    ETREE_VERSION = ET_ORIG.VERSION
except ImportError:
    import xml.etree.ElementTree as ET
    ETREE_VERSION = ET.VERSION

ETREE_VERSION = [int(i) for i in ETREE_VERSION.split(".")]

current_path = os.path.abspath(os.getcwd())

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"

def cleaner_unicode(string):
    if string is not None:
        return string.encode('ascii', errors='backslashreplace')
    else:
        return string

def cleaner_results(string):

    try:
        q = re.compile(r'<.*?>', re.IGNORECASE)
        return re.sub(q, '', string)

    except:
        return ''

def get_urls(string):
    urls = re.findall(r'href=[\'"]?([^\'" >]+)', string)
    return urls


class NetsparkerCloudXmlParser(object):
    """
    The objective of this class is to parse an xml file generated by the netsparkercloud tool.

    TODO: Handle errors.
    TODO: Test netsparkercloud output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param netsparkercloud_xml_filepath A proper xml generated by netsparkercloud
    """

    def __init__(self, xml_output):
        self.filepath = xml_output

        tree = self.parse_xml(xml_output)
        if tree:
            self.items = [data for data in self.get_items(tree)]
        else:
            self.items = []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError, err:
            self.devlog("SyntaxError: %s. %s" % (err, xml_output))
            return None

        return tree

    def get_items(self, tree):
        """
        @return items A list of Host instances
        """
        for node in tree.findall("vulnerabilities/vulnerability"):
            yield Item(node)


class Item(object):
    """
    An abstract representation of a Item


    @param item_node A item_node taken from an netsparkercloud xml tree
    """

    def __init__(self, item_node):
        self.node = item_node
        self.url = self.get_text_from_subnode("url")

        host = re.search(
            "(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$", self.url)

        self.protocol = host.group(1)
        self.hostname = host.group(4)
        self.port = 80

        if self.protocol == 'https':
            self.port = 443
        if host.group(11) is not None:
            self.port = host.group(11)

        self.type = self.get_text_from_subnode("type")
        self.name = self.get_text_from_subnode("name")
        self.severity = self.get_text_from_subnode("severity")
        self.certainty = self.get_text_from_subnode("certainty")


        self.node = item_node.find("http-request")
        self.method = self.get_text_from_subnode("method")
        self.request = self.get_text_from_subnode("content")

        #print self.node
        self.param = ""
        self.paramval = ""
        for p in self.node.findall("parameters/parameter"):
            self.param = p.get('name')
            self.paramval = p.get('value')

        self.node = item_node.find("http-response")
        self.response = self.get_text_from_subnode("content")

        self.extra = []
        for v in item_node.findall("extra-information/info"):
            self.extra.append(v.get('name') + ":" + v.get('value') )

        self.node = item_node.find("classification")
        self.owasp = self.get_text_from_subnode("owasp")
        self.wasc = self.get_text_from_subnode("wasc")
        self.cwe = self.get_text_from_subnode("cwe")
        self.capec = self.get_text_from_subnode("capec")
        self.pci = self.get_text_from_subnode("pci31")
        self.pci2 = self.get_text_from_subnode("pci32")
        self.hipaa = self.get_text_from_subnode("hipaa")

        self.ref = []
        if self.cwe:
            self.ref.append("CWE-" + self.cwe)
        if self.owasp:
            self.ref.append("OWASP-" + self.owasp)

        self.node = item_node
        self.remedyreferences = self.get_text_from_subnode("remedy-references")
        self.externalreferences = self.get_text_from_subnode("external-references")
        if self.remedyreferences:
            for u in get_urls(self.remedyreferences):
                self.ref.append(u)
        if self.externalreferences:
            for u in get_urls(self.externalreferences):
                self.ref.append(u)

        self.impact = cleaner_results(self.get_text_from_subnode("impact"))
        self.remedialprocedure = cleaner_results(self.get_text_from_subnode("remedial-procedure"))
        self.remedialactions = cleaner_results(self.get_text_from_subnode("remedial-actions"))
        self.exploitationskills = cleaner_results(self.get_text_from_subnode("exploitation-skills"))
        self.proofofconcept = cleaner_results(self.get_text_from_subnode("proof-of-concept"))

        self.resolution = self.remedialprocedure
        self.resolution +=  "\nRemedial Actions: " + self.remedialactions if self.remedialactions is not None else ""
        

        self.desc = cleaner_results(self.get_text_from_subnode("description"))
        self.desc += "\nImpact: " + self.impact if self.impact else ""
        self.desc += "\nExploitation Skills: " + self.exploitationskills if self.exploitationskills else ""
        self.desc += "\nProof of concept: " + self.proofofconcept if self.proofofconcept else ""
        self.desc += "\nWASC: " + self.wasc if self.wasc else ""
        self.desc += "\nPCI31: " + self.pci if self.pci else ""
        self.desc += "\nPCI32: " + self.pci2 if self.pci2 else ""
        self.desc += "\nCAPEC: " + self.capec if self.capec else ""
        self.desc += "\nHIPA: " + self.hipaa if self.hipaa else ""
        self.desc += "\nExtra: " + "\n".join(self.extra) if self.extra else ""

    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        if self.node:
            sub_node = self.node.find(subnode_xpath_expr)
            if sub_node is not None:
                if sub_node.text is not None:
                    return cleaner_unicode(sub_node.text)

        return ""


class NetsparkerCloudPlugin(core.PluginBase):
    """
    Example plugin to parse netsparkercloud output.
    """

    def __init__(self):
        core.PluginBase.__init__(self)
        self.id = "NetsparkerCloud"
        self.name = "NetsparkerCloud XML Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "NetsparkerCloud"
        self.framework_version = "1.0.0"
        self.options = None
        self._current_output = None
        self._command_regex = re.compile(
            r'^(sudo netsparkercloud|\.\/netsparkercloud).*?')

        global current_path
        self._output_file_path = os.path.join(self.data_path,
                                              "netsparkercloud_output-%s.xml" % self._rid)

    def resolve(self, host):
        try:
            return socket.gethostbyname(host)
        except:
            pass
        return host

    def parseOutputString(self, output, debug=False):

        parser = NetsparkerCloudXmlParser(output)
        first = True
        for i in parser.items:
            if first:
                ip = self.resolve(i.hostname)
                h_id = self.createAndAddHost(ip)
                i_id = self.createAndAddInterface(
                    h_id, ip, ipv4_address=ip, hostname_resolution=i.hostname)

                s_id = self.createAndAddServiceToInterface(h_id, i_id, str(i.port),
                                                           str(i.protocol),
                                                           ports=[str(i.port)],
                                                           status="open")

                n_id = self.createAndAddNoteToService(
                    h_id, s_id, "website", "")
                n2_id = self.createAndAddNoteToNote(
                    h_id, s_id, n_id, i.hostname, "")
                first = False

            v_id = self.createAndAddVulnWebToService(h_id, s_id, i.name, ref=i.ref, website=i.hostname,
                                                     severity=i.severity, desc=i.desc, path=i.url, method=i.method,
                                                     request=i.request, response=i.response, resolution=i.resolution, pname=i.param)

        del parser

    def processCommandString(self, username, current_path, command_string):
        return None

    def setHost(self):
        pass


def createPlugin():
    return NetsparkerCloudPlugin()

if __name__ == '__main__':
    parser = NetsparkerCloudXmlParser(sys.argv[1])
    for item in parser.items:
        if item.status == 'up':
            print item
