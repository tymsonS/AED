import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client
from django.utils.html import conditional_escape
from pytest_bdd import scenarios

from mcod.showcases.admin import ShowcaseProposalAdmin, ShowcaseProposalTrashAdmin
from mcod.showcases.models import Showcase, ShowcaseProposal, ShowcaseProposalTrash

scenarios(
    "features/showcase_details_admin.feature",
    "features/showcases_list_admin.feature",
    "features/showcaseproposal_details_admin.feature",
    "features/showcaseproposal_list_admin.feature",
)


@pytest.mark.parametrize(
    ("admin_class", "model_class"),
    (
        (ShowcaseProposalAdmin, ShowcaseProposal),
        (ShowcaseProposalTrashAdmin, ShowcaseProposalTrash),
    ),
)
def test_external_datasets_admin_preserves_valid_links_escapes_titles_and_skips_invalid_urls(admin_class, model_class):
    event_handler = "onerror"
    xss_script = "alert(document.cookie)"
    poisoned_title = f'<img src=x {event_handler}="{xss_script}">'
    obj = model_class(
        external_datasets=[
            {
                "title": poisoned_title,
                "url": "https://example.com/first?one=1&two=2",
            },
            {"title": "Second dataset", "url": "https://example.org/second"},
            {"title": "Unsafe dataset", "url": "javascript:alert(document.cookie)"},
        ]
    )

    rendered = admin_class(model_class, AdminSite()).external_datasets_admin(obj)

    assert str(rendered) == (
        '<a href="https://example.com/first?one=1&amp;two=2" target="_blank" rel="noopener noreferrer">'
        f"&lt;img src=x {event_handler}=&quot;{xss_script}&quot;&gt;</a><br>"
        '<a href="https://example.org/second" target="_blank" rel="noopener noreferrer">Second dataset</a>'
    )

    # Check that Django preserves the safely rendered HTML without escaping it again.
    assert conditional_escape(rendered) == rendered


def test_external_datasets_admin_handles_null_value():
    obj = ShowcaseProposal(external_datasets=None)

    assert ShowcaseProposalAdmin(ShowcaseProposal, AdminSite()).external_datasets_admin(obj) == "-"


def test_external_datasets_admin_skips_item_with_null_url():
    obj = ShowcaseProposal(
        external_datasets=[
            {"title": "Invalid dataset", "url": None},
            {"title": "Valid dataset", "url": "https://example.com"},
        ]
    )

    rendered = ShowcaseProposalAdmin(
        ShowcaseProposal,
        AdminSite(),
    ).external_datasets_admin(obj)

    assert str(rendered) == '<a href="https://example.com" target="_blank" rel="noopener noreferrer">Valid dataset</a>'


def test_save_model_given_created_by(admin, another_admin):
    obj = {
        "category": "app",
        "license_type": "free",
        "title": "Test with dataset title 1",
        "slug": "manual-name-1",
        "notes": "tresc",
        "status": "published",
        "url": "http://1.test.pl",
    }

    obj2 = {
        "category": "app",
        "license_type": "free",
        "title": "Test with dataset title 2",
        "slug": "manual-name-2",
        "notes": "tresc",
        "status": "published",
        "url": "http://2.test.pl",
    }

    obj3 = {
        "category": "app",
        "license_type": "free",
        "title": "Test with dataset title 3",
        "slug": "manual-name-1",
        "notes": "tresc",
        "status": "published",
        "url": "http://1.test.pl",
    }

    # add 1 showcase
    client = Client()
    client.force_login(admin)
    response = client.post(Showcase.get_admin_add_url(), obj, follow=True)
    assert response.status_code == 200
    ap1 = Showcase.objects.last()
    assert ap1.created_by.id == admin.id

    # add 2 showcase
    client = Client()
    client.force_login(another_admin)
    response = client.post(Showcase.get_admin_add_url(), obj2, follow=True)
    assert response.status_code == 200
    ap2 = Showcase.objects.last()
    assert ap2.created_by.id == another_admin.id
    assert ap1.id != ap2.id

    # change 1 showcase
    client = Client()
    client.force_login(another_admin)
    response = client.post(ap1.admin_change_url, obj3, follow=True)
    assert response.status_code == 200

    # creator of app2 should be still admin
    assert Showcase.objects.get(id=ap1.id).created_by.id == admin.id


def test_add_tags_to_showcases(admin, tag, tag_pl, showcase):
    data = {
        "category": "app",
        "license_type": "free",
        "title": "Test with dataset title",
        "slug": "name",
        "notes": "tresc",
        "url": "http://test.pl",
        "status": "published",
        "tags_pl": [tag_pl.id],
    }

    assert tag_pl not in showcase.tags.all()
    client = Client()
    client.force_login(admin)
    client.post(showcase.admin_change_url, data, follow=True)
    obj = Showcase.objects.get(id=showcase.id)
    assert obj.slug == "name"
    assert tag_pl in showcase.tags.all()
