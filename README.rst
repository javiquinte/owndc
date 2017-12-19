# owndc
FDSN-WS Dataselect for the seismological community which allows the access to any data centre.

Purpose
-------

owndc was originally designed to give a SeisComP3 user access to waveforms in any data centre in the world.
It provides a fully complaint FDSN-WS Dataselect interface, which is compatible with any standard client
using this type of service.

In SeisComP3, the results from the FDSN-WS Station are not needed. Mainly because the metadata must be already
loaded in the SC3 database. This is the main reason why we do not provide also support for the Station-WS service.

It provides an automatic way to configure it to access all data stored at EIDA nodes.

Very, very quick installation instructions
------------------------------------------

Using pip
=========
Execute the following commands to deploy [owndc from Pypi](https://pypi.python.org/pypi/owndc).

```
$ pip install owndc
$ python -m owndc
```


From the Github repository
==========================
The execution of the following commands will deploy and setup a ready-to-run
owndc instance with access to all the data within
[EIDA](http://www.orfeus-eu.org/eida/).

```
$ git clone https://github.com/javiquinte/owndc
$ cd owndc
$ cp owndc.cfg.sample owndc.cfg
$ cd data
$ python owndcupdate.py
$ cd ..
$ ./owndc.py
```

Create the owndc documentation
------------------------------

Very detailed instructions regarding installation as well as different aspects
of the software can be found in the official documentation provided in this
repository. In order to generate it you should execute these commands:

```
$ cd doc
$ make latexpdf
$ evince _build_/latex/owndc.pdf
```

