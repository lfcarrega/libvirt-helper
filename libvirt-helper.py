#!/usr/bin/env python

import argparse
try:
    import libvirt
except ImportError as err:
    raise err
import os
import re
import subprocess
import sys
from xml.dom import minidom

def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def libvirt_connect():
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as err:
        print("Failed to open connection to the hypervisor!", file=sys.stderr)
        raise err
    return conn

def domain_connect(conn=None, domainName=None):
    if domainName != None:
        if conn == None:
            conn = libvirt_connect()
        domainConn = conn.lookupByName(domainName)
        return domainConn

def list_domains(conn=None, active=None):
    if conn == None:
        conn = libvirt_connect()
    if active:
        domainList = conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE)
    else:
        domainList = conn.listAllDomains()
    domainNameList = []
    for domain in domainList:
        domainNameList.append(domain.name())
    return conn, domainNameList

def list_usb():
    # thanks to River, meson10 and MikeiLL from https://stackoverflow.com/questions/8110310/simple-way-to-query-connected-usb-devices-info-in-python
    device_re = re.compile("Bus\\s+(?P<bus>\\d+)\\s+Device\\s+(?P<device>\\d+).+ID\\s(?P<id>\\w+:\\w+)\\s(?P<tag>.+)$", re.I)
    df = str(subprocess.check_output("lsusb"), 'utf-8')
    devices = []
    for i in df.split('\n'):
        if i:
            info = device_re.match(i)
            if info:
                dinfo = info.groupdict()
                dinfo['device'] = '/dev/bus/usb/%s/%s' % (dinfo.pop('bus'), dinfo.pop('device'))
                devices.append(dinfo)
    devicesList = []
    devicesListId = []
    for dev in devices:
        tag = dev["tag"]
        id = dev["id"]
        devicesList.append(f"{tag} ({id})")
        devicesListId.append(f"{id}")
    return devices, devicesListId, devicesList

def domain_validate(domain):
    conn, domainNameList = list_domains()
    if domain in domainNameList:
        return conn, domain
    else:
        die(f"Domain {domain} does not exist!")

def usb_validate(usb):
    devices, devicesListId, devicesList = list_usb()
    usbList = usb.split(",")
    validUsbList = []
    for dev in usbList:
        if dev in devicesListId:
            validUsbList.append(dev)
        else:
            print(f"Invalid USB device: {dev}", file=sys.stderr)
    if len(validUsbList) == 0:
        die(f"Missing USB devices to attach!")
    else:
        return validUsbList

def domain_picker():
    if not args.domain or args.domain == "?":
        conn, domainNameList = list_domains()
        if len(domainNameList) > 0:
            for index, domain in enumerate(domainNameList):
                print(f"{index}. {domain}")
        domainChoose = input("Pick the desired domain: ")
        if domainChoose.isdigit() and int(domainChoose) < len(domainNameList):
            domainChoosen = domainNameList[int(domainChoose)]
        elif domainChoose in domainNameList:
            domainChoosen = domainChoose
    else:
        conn, domainChoosen = domain_validate(args.domain)
    return conn, domainChoosen

def usb_picker():
    if not args.usb or args.usb == "?":
        devices, devicesListId, devicesList = list_usb()
        usbList = []
        for index, dev in enumerate(devicesList):
            print(f"{index}. {dev}")
        usbChoose = input("Pick the desired USB devices: ")
        usbChooseList = usbChoose.split(",")
        for choose in usbChooseList:
            if choose.isdigit() and int(choose) > len(devicesListId):
                print(f"Invalid option: {choose}", file=sys.stderr)
            elif choose.isdigit():
                id = devicesListId[int(choose)]
                usbList.append(id)
            elif choose in devicesListId:
                usbList.append(choose)
    else:
        usbList = usb_validate(args.usb)
    return usbList

def build_xml(vendorID=None, productID=None, isoPath=None):
    if vendorID != None and productID != None:
        root = minidom.Document()
        hostdev = root.createElement('hostdev')
        hostdev.setAttribute('mode', 'subsystem')
        hostdev.setAttribute('type', 'usb')
        hostdev.setAttribute('managed', 'yes')
        root.appendChild(hostdev)

        source = root.createElement('source')
        hostdev.appendChild(source)

        vendor = root.createElement('vendor')
        vendor.setAttribute('id', '0x'+vendorID)
        source.appendChild(vendor)

        product = root.createElement('product')
        product.setAttribute('id', '0x'+productID)
        source.appendChild(product)

        root = root.childNodes[0]
        xml = root.toprettyxml()
    return xml

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--list-domains", help="list domains - only names for now", action="store_true")
parser.add_argument("-u", "--list-usb", help="list usb devices", action="store_true")
parser.add_argument("-a", "--attach-usb", help="attach usb device(s)", action="store_true")
parser.add_argument("-d", "--detach-usb", help="detach usb device(s)", action="store_true")
parser.add_argument("--udev", help="create udev rule/auto attach device on plug", action="store_true")
parser.add_argument("domain", default=None, nargs="?", type=str, metavar=("DOMAIN"))
parser.add_argument("usb", default=None, nargs="?", type=str, metavar=("USB_ID1,USB_ID2"))
args = parser.parse_args()

if len(sys.argv)==1:
    parser.print_help(sys.stderr)
    sys.exit(1)

if args.udev:
    ignoreList="/etc/libvirt-helper/usb-ignorelist.conf"
    ignore=False
    if not args.domain:
        conn, domainNameList = list_domains(active=True)
        domain = domainNameList[0]
    domainConn = domain_connect(domainName=domain)
    if os.environ.get('PRODUCT'):
        product_list = os.environ.get('PRODUCT').split("/")
        vendorId = product_list[0].rjust(4, "0")
        productId = product_list[1].rjust(4, "0")
        usbId = f"{vendorId}:{productId}"
    xml = build_xml(vendorID=vendorId, productID=productId)
    if os.path.exists(ignoreList):
        with open(ignoreList, "r") as file:
            for line in file:
                if line.strip() == usbId:
                    ignore=True
    if os.environ.get('ACTION') == "add" and not ignore:
        domainConn.attachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)
    if os.environ.get('ACTION') == "remove" and not ignore:
        domainConn.detachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

if args.attach_usb or args.detach_usb:
    conn, domain = domain_picker()
    domainConn = domain_connect(conn=conn, domainName=domain)
    usb = usb_picker()
    print(f"Domain: {domain}")
    print(f"USB devices: {usb}")
    validDev = []
    invalidDev = []
    if domain != None and usb != None:
        for index, dev in enumerate(usb):
            devId = dev.split(":")
            vendorId = devId[0]
            productId = devId[1]
            xml = build_xml(vendorID=vendorId, productID=productId)
            try:
                if args.attach_usb and not args.detach_usb:
                    domainConn.attachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)
                if args.detach_usb and not args.attach_usb:
                    domainConn.detachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)
                if args.attach_usb and args.detach_usb:
                    domainConn.detachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)
                    domainConn.attachDeviceFlags(xml, libvirt.VIR_DOMAIN_AFFECT_CURRENT)
            except libvirt.libvirtError as err:
                msg = err.get_error_message()
                if msg.find("domain is not running") > -1:
                    sys.exit(1)
                else:
                    invalidDev.append(dev)
            else:
                validDev.append(dev)
    if args.attach_usb and not args.detach_usb:
        if len(validDev) > 0:
            print(f"Attached devices: {validDev}")
        if len(invalidDev) > 0:
            print(f"Failed to attach these devices: {invalidDev}")
    if args.detach_usb and not args.attach_usb:
        if len(validDev) > 0:
            print(f"Detached devices: {validDev}")
        if len(invalidDev) > 0:
            print(f"Failed to detach these devices: {invalidDev}")
    if args.attach_usb and args.detach_usb:
        if len(validDev) > 0:
            print(f"Reattached devices: {validDev}")
        if len(invalidDev) > 0:
            print(f"Failed to reattach these devices: {invalidDev}")
    sys.exit(0)

if args.list_domains:
    conn, domainNameList = list_domains()
    if len(domainNameList) > 0:
        for domain in domainNameList:
            print(f"{domain}")
    sys.exit(0)

if args.list_usb:
    devices, devicesListId, devicesList = list_usb()
    for dev in (devicesList):
        print(f"{dev}")
    sys.exit(0)
