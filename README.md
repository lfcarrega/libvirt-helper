# Dependencies
* Python
* libvirt lib from the libvirt-python package of your distro
* lsusb from the usbutils package of your distro

# Usage
```
usage: libvirt-helper.py [-h] [-l] [-u] [-a] [-d] [--udev] [DOMAIN] [USB_ID1,USB_ID2]

positional arguments:
  DOMAIN
  USB_ID1,USB_ID2

options:
  -h, --help          show this help message and exit
  -l, --list-domains  list domains - only names for now
  -u, --list-usb      list usb devices
  -a, --attach-usb    attach usb device(s)
  -d, --detach-usb    detach usb device(s)
  --udev              create udev rule/auto attach device on plug
```

# Examples
Attach using `fzf` to pick the domain and the built-in picker for the USB device
```shell
libvirt-helper.py -a $(libvirt-helper.py -l | fzf)
```

Attach a USB device to the domain named win11 using the built-in device picker
```shell
libvirt-helper.py -a win11
```

Attach multiple USB devices to a domain named win11
```shell
libvirt-helper.py -a win11 1532:028f,1532:0099,2dc8:3109
```

Attach using the built-in domain and device picker
```shell
libvirt-helper.py -a
```

Attach and detach with an udev rule `/etc/udev/rules.d/99-libvirt-helper.rules`
```shell
SUBSYSTEM=="usb", ACTION=="add|remove", RUN+="/path/to/libvirt-helper.py --udev"
```



