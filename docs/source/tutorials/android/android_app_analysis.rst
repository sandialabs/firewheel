.. _android-app-analysis:

************************
Post-Experiment Analysis
************************

This optional section shows how to inspect data collected from the Android
application after the experiment.

It assumes that you have already run the updated experiment from
:ref:`android-app-automation` and that the collected Kiwix data exists at:

.. code-block:: text

    /scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone

The analysis here is intentionally lightweight. The goal is to show how to
confirm that the application loaded the staged ZIM file and persisted useful
state during the experiment.

Inspecting the File Tree
========================

Set a shell variable for convenience:

.. code-block:: bash

    export APP_DATA=/scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone

Start with a directory listing:

.. code-block:: bash

    tree "$APP_DATA"

If `tree <https://linux.die.net/man/1/tree>`_ is not installed, use `find <https://linux.die.net/man/1/find>`_ instead:

.. code-block:: bash

    find "$APP_DATA" -maxdepth 4 -print | sort

A typical Kiwix data directory from this tutorial contains:

.. code-block:: text

    /scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone
    ├── app_webview/
    ├── cache/
    ├── databases/
    │   ├── KiwixRoom.db
    │   ├── KiwixRoom.db-shm
    │   ├── KiwixRoom.db-wal
    │   ├── LibGlobalFetchLib.db
    │   ├── LibGlobalFetchLib.db-shm
    │   └── LibGlobalFetchLib.db-wal
    ├── files/
    │   ├── icu/
    │   ├── logs/
    │   ├── objectbox/
    │   └── profileInstalled
    └── shared_prefs/
        ├── AwOriginVisitLoggerPrefs.xml
        ├── clickedNoThanks.xml
        ├── kiwix-mobile.xml
        ├── org.kiwix.kiwixmobile.standalone_preferences.xml
        └── WebViewChromiumPrefs.xml

The two most relevant areas for this tutorial are:

``databases/``
    Contains SQLite databases used by the application.

``shared_prefs/``
    Contains XML preference files. These often record application configuration
    and recently selected state.

Setting Up Python Analysis
==========================

Create or use a Python environment with ``pandas`` available.

.. code-block:: bash

    source /opt/firewheel/fwpy/bin/activate
    python -m pip install pandas


Discover the SQLite Databases
=============================

The following script lists SQLite database files and their tables.

.. code-block:: python
    :caption: discover_databases.py

    import sqlite3
    from pathlib import Path

    import pandas as pd


    data_dir = Path(
        "/scratch/firewheel/transfers/android-phone/data/data/"
        "org.kiwix.kiwixmobile.standalone"
    )

    db_candidates = sorted(
        path for path in data_dir.rglob("*")
        if path.is_file() and path.suffix in {".db", ".sqlite", ".sqlite3"}
    )

    print(f"Found {len(db_candidates)} database candidate(s).")

    for db_path in db_candidates:
        print(f"\n{'=' * 80}")
        print(f"Database: {db_path}")
        print(f"{'=' * 80}")

        conn = sqlite3.connect(db_path)

        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            conn,
        )

        print("\nTables:")
        print(tables.to_string(index=False))

        conn.close()

Run it with:

.. code-block:: bash

    python discover_databases.py

Expected output should be similar to:

.. code-block:: text

    Found 2 database candidate(s).

    ================================================================================
    Database: /scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone/databases/KiwixRoom.db
    ================================================================================

    Tables:
                      name
        DownloadRoomEntity
         HistoryRoomEntity
           NotesRoomEntity
    RecentSearchRoomEntity
      WebViewHistoryEntity
          android_metadata
         room_master_table
           sqlite_sequence

    ================================================================================
    Database: /scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone/databases/LibGlobalFetchLib.db
    ================================================================================

    Tables:
                 name
     android_metadata
             requests
    room_master_table

Inspect Kiwix History State
===========================

The main database of interest is usually:

.. code-block:: text

    databases/KiwixRoom.db

We will inspect two of the tables:

``HistoryRoomEntity``
    Records Kiwix reader history, including the ZIM identifier, page URL, page
    title, and related metadata.

``WebViewHistoryEntity``
    Records WebView navigation state.

Use the following script to inspect those tables.

.. code-block:: python
    :caption: inspect_kiwix_history.py

    import sqlite3
    from pathlib import Path

    import pandas as pd


    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 120)
    pd.set_option("display.width", 240)

    db_path = Path(
        "/scratch/firewheel/transfers/android-phone/data/data/"
        "org.kiwix.kiwixmobile.standalone/databases/KiwixRoom.db"
    )

    conn = sqlite3.connect(db_path)

    print(f"Database: {db_path}")

    history = pd.read_sql(
        """
        SELECT
            id,
            zimId,
            zimName,
            zimFilePath,
            historyUrl,
            historyTitle,
            dateString,
            timeStamp
        FROM HistoryRoomEntity
        ORDER BY id
        """,
        conn,
    )

    print("\nHistoryRoomEntity:")
    if history.empty:
        print("No history rows found.")
    else:
        print(history.to_string(index=False))

    webview_history = pd.read_sql(
        """
        SELECT
            id,
            zimId,
            webViewIndex,
            webViewCurrentPosition,
            length(webViewBackForwardListBundle) AS bundleBytes
        FROM WebViewHistoryEntity
        ORDER BY id
        """,
        conn,
    )

    print("\nWebViewHistoryEntity:")
    if webview_history.empty:
        print("No WebView history rows found.")
    else:
        print(webview_history.to_string(index=False))

    conn.close()

Run it with:

.. code-block:: bash

    python inspect_kiwix_history.py

A successful tutorial run should show something similar to:

.. code-block:: text

    Database: /scratch/firewheel/transfers/android-phone/data/data/org.kiwix.kiwixmobile.standalone/databases/KiwixRoom.db

    HistoryRoomEntity:
     id                                zimId               zimName zimFilePath                         historyUrl     historyTitle  dateString     timeStamp
      1 21d71319-166f-c82c-f34f-b48739f38bc2 wikipedia_en_computer        None https://kiwix.app/Computer_science Computer science 11 Aug 2026 1786479864686

    WebViewHistoryEntity:
     id                                zimId  webViewIndex  webViewCurrentPosition  bundleBytes
      4 21d71319-166f-c82c-f34f-b48739f38bc2             0                       0         1904

This confirms that Kiwix opened content from the staged ZIM file. In this run,
``HistoryRoomEntity`` recorded the page title and URL, while the selected ZIM
file path was recorded in shared preferences.


The ``WebViewHistoryEntity`` table should also contain a row for the same
``zimId``. Its WebView navigation bundle is binary, so this tutorial only prints
its size rather than attempting to decode it.

Inspect Shared Preferences
==========================

Shared preferences are XML files under ``shared_prefs/``. For this tutorial,
``kiwix-mobile.xml`` is especially useful because it records the current ZIM file
path.

Use the following script to inspect preference files.

.. code-block:: python
    :caption: inspect_preferences.py

    from pathlib import Path
    import xml.etree.ElementTree as ET


    data_dir = Path(
        "/scratch/firewheel/transfers/android-phone/data/data/"
        "org.kiwix.kiwixmobile.standalone"
    )

    pref_files = sorted(data_dir.rglob("shared_prefs/*.xml"))

    print(f"Found {len(pref_files)} shared-preference file(s).")

    for pref_file in pref_files:
        print(f"\n{'=' * 80}")
        print(f"Preferences: {pref_file.name}")
        print(f"{'=' * 80}")

        try:
            tree = ET.parse(pref_file)
            root = tree.getroot()

            for child in root:
                name = child.attrib.get("name", "<unnamed>")
                value = child.attrib.get("value", child.text)

                if name == "currentzimfile" or "zim" in name.lower():
                    print(f"{child.tag}: {name} = {value}")

        except Exception as exc:
            print(f"Could not parse {pref_file}: {exc}")

Run it with:

.. code-block:: bash

    python inspect_preferences.py

A successful run should show something similar to:

.. code-block:: text

    Found 5 shared-preference file(s).

    ================================================================================
    Preferences: AwOriginVisitLoggerPrefs.xml
    ================================================================================

    ================================================================================
    Preferences: WebViewChromiumPrefs.xml
    ================================================================================

    ================================================================================
    Preferences: clickedNoThanks.xml
    ================================================================================

    ================================================================================
    Preferences: kiwix-mobile.xml
    ================================================================================
    string: currentzimfile = /storage/emulated/0/Download/Kiwix/wikipedia_en_computer_nopic_2026-06.zim

    ================================================================================
    Preferences: org.kiwix.kiwixmobile.standalone_preferences.xml
    ================================================================================

The ``currentzimfile`` entry is a useful confirmation that Kiwix selected the
offline ZIM file staged by FIREWHEEL.


Important Limitations
=====================

Keep these limitations in mind:

* Mobile app schemas change between versions.
* First-run application behavior may differ by environment.
* The ZIM content file is large and was staged on Android shared storage, not
  inside the private app data directory.

.. seealso::

    For more information on launching Android experiments please review the documentation for :ref:`android_mc_repo`.

