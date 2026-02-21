Changelog
=========

Next
----

2026.02.21
----------


- Add ``VuMarkTarget`` class for VuMark template targets, alongside the renamed ``ImageTarget`` class (previously ``Target``).
  ``ImageTarget`` is for image-based targets and ``VuMarkTarget`` is for VuMark template targets.
  Both can be stored in a ``VuforiaDatabase``.

2026.02.18.2
------------


2026.02.18.1
------------


2026.02.18
----------


2026.02.15.5
------------


2026.02.15.4
------------


- Add ``sleep_fn`` parameter to ``MockVWS`` for injecting a custom delay strategy, enabling deterministic and fast tests without monkey-patching.

2026.02.15.3
------------


- Add ``response_delay_seconds`` parameter to ``MockVWS`` for simulating slow server responses and testing timeout handling.
- Add ``response_delay_seconds`` setting to the Flask mock (``VWSSettings`` and ``VWQSettings``) for simulating slow server responses.

2025.03.10.1
------------

2025.03.10
----------

2025.02.21
----------

2025.02.18
----------

2024.08.30
------------

2024.07.15
------------

- Support passing data as strings.

2024.07.02.1
------------

- Fix installation on Windows now that ``numpy`` 2.0.0 has been released.

2024.02.16
------------

- Add a structural similarity image matcher.

2018.12.01.0
------------

- Distribute type information.

2018.09.10.0
------------

- Initial release
