.. OwnDC documentation master file, created by
   sphinx-quickstart on Thu Sep 24 07:49:51 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to OwnDC's documentation!
=================================

Contents:

.. toctree::
   :maxdepth: 2


Roadmap and things to do
========================

 #. Transfer repository to GEOFON Organization
 #. Fix the incompatibility with scolv
 #. Add to the SeisComP3 Github repository
 #. Add the Station WS also

.. todo:: blah, blah

Installation
============

Requirements
------------

 * Python 2.7
   
.. _download:

Download
--------

OwnDC can be downloaded from its Github repository at https://github.com/javiquinte/owndc.
[Eventually it may be also included in the SeisComP3 distribution.] 

To clone the repository, you only need to use the *git* utility. ::

  $ git clone https://github.com/javiquinte/owndc

Then, change to the ``owndc`` directory and follow the instructions in the
next section to properly configure it. ::

  $ cd owndc

Configuration
-------------

Configuration options
^^^^^^^^^^^^^^^^^^^^^

The first step before starting to use OwnDC is to configure a the `verbosity`
option for this service. The configuration file must be located in the root
directory of your installation (f.i. ``./ownDC.cfg``). A sample version is
provided under ``./ownDC.cfg.sample``. You can copy it and edit it to fit your
needs. ::

  $ cp ownDC.cfg.sample ownDC.cfg
  $ vi ownDC.cfg

`verbosity` controls the amount of output send to the logging system depending
of the importance of the messages. The levels are: CRITICAL, ERROR, WARNING,
INFO and DEBUG.

.. _service_configuration:

.. code-block:: ini

    [Service]
    verbosity = INFO

Routes
^^^^^^

To start using OwnDC you need to declare which networks (streams) you want to
use and the locations of the services. We provide a script to get an
automatic configuration specifying an updated state of the EIDA routing
table. To see all the available options you can call the script with the ``-h``
parameter. ::

  $ cd data
  $ python getEIDAconfig.py -h

If you would like to use this automatic configuration, just call the script in
the following way: ::

  $ python getEIDAconfig.py

When the script finishes you should find a file called ``ownDC-routes.xml``
containing all the routes to get data from any EIDA node.

If you would like to route some other streams not included in EIDA,
there is a *masterTable* that can be used. When the service starts, it
checks if a file called ``masterTable.xml`` in the ``data`` folder exists. If
this is the case, the file is read, the routes inside are loaded in a separate
table and are given the **maximum priority**.
This fits quite well with requests to other datacenters, whose internal
structure is not well known.

If you would like to configure extra routes, you need to create the
``masterTable.xml`` file. A sample version of the file can be copied from the
Routing Service code and later edited. ::

  $ cp masterTable.xml.sample masterTable.xml


.. warning:: Only the network level is used to calculate the
             routing for the routes in the master table. This makes sense if
             we consider that the main purpose of this *extra* information is
             to be able to route requests to datacenters, whose internal and
             more specific distribution of data to levels deeper than the
             network are usually not known.

In the following example, we show how to point to the service in IRIS, when
the ``II`` network is requested.

.. code-block:: xml

    <?xml version="1.0" encoding="utf-8"?>
    <ns0:routing xmlns:ns0="http://geofon.gfz-potsdam.de/ns/Routing/1.0/">
        <ns0:route locationCode="" networkCode="II" stationCode="" streamCode="">
            <ns0:dataselect address="service.iris.edu/fdsnws/dataselect/1/query"
                end="" priority="9" start="1980-01-01T00:00:00.0000Z" />
        </ns0:route>
    </ns0:routing>

.. warning:: The `priority` attribute will be valid only in the context of the
             `masterTable`. There is no relation with the priority for a
             similar route that could be in the normal routing table.

Documentation for developers
============================

Query module
------------

.. automodule:: query

DataSelectQuery class
^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: query.DataSelectQuery
   :members:
   :undoc-members:

ResultFile class
^^^^^^^^^^^^^^^^

.. autoclass:: query.ResultFile
   :members:
   :undoc-members:

Routing module
--------------

.. automodule:: routing
   :members:
   :undoc-members:

Utils module
------------

.. automodule:: utils

Route class
^^^^^^^^^^^

.. autoclass:: utils.Route
   :members:
   :undoc-members:

Stream class
^^^^^^^^^^^^

.. autoclass:: utils.Stream
   :members:
   :undoc-members:

TW (timewindow)  class
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: utils.TW
   :members:
   :undoc-members:

RouteMT class
^^^^^^^^^^^^^

.. autoclass:: utils.RouteMT
   :members:
   :undoc-members:

RequestMerge class
^^^^^^^^^^^^^^^^^^

.. autoclass:: utils.RequestMerge
   :members:
   :undoc-members:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

