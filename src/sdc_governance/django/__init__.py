"""
Django integration for SDC Governance.

Optional subpackage providing middleware, signals, and admin integration
for Django applications. Install with::

    pip install sdc-governance[django]

Add to INSTALLED_APPS::

    INSTALLED_APPS = [
        ...
        'sdc_governance.django',
    ]

Add middleware::

    MIDDLEWARE = [
        ...
        'sdc_governance.django.middleware.GovernanceMiddleware',
    ]
"""
