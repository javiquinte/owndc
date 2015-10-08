# OwnDC
FDSN-WS Dataselect for the seismological community which allows the access any datacentre

Purpose
-------

OwnDC was originally designed to give a SeisComP3 user access to waveforms in any datacentre in the world.
It provides a fully complaint FDSN-WS Dataselect interface, which is compatible with any standard client
using this type of service.

In SeisComP3, the results from the FDSN-WS Station is not needed. Mainly because the metadata must be already
loaded in the SC3 database. This is the main reason why we do not provide also support for the Station service.

It provides an automatic way to configure it to access all data stored at EIDA nodes.

Very, very quick installation instructions
------------------------------------------

```
$ git clone https://github.com/javiquinte/owndc
$ cd owndc
$ cp ownDC.cfg.sample ownDC.cfg
$ cd data
$ python getEIDAconfig.py
$ ./ownDC.py
```
