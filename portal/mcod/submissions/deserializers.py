from django.utils.translation import gettext_lazy as _
from marshmallow import ValidationError, validate, validates_schema

from mcod.core.api import fields as core_fields
from mcod.core.api.jsonapi.deserializers import ObjectAttrs, TopLevel
from mcod.submissions.models import Category, Subject

GENERIC_SUBMISSION_ALLOWED_CATEGORIES = {
    Subject.DATA: [
        Category.SHARING,
        Category.STANDARDS,
        Category.HVD,
        Category.DGA,
        Category.OTHER,
    ],
    Subject.PORTAL: [
        Category.FEATURES,
        Category.PROFILES,
        Category.PERMISSIONS,
        Category.BUGS,
        Category.OTHER,
    ],
    Subject.DATA_PROTECTION: [],
    Subject.LEGAL: [],
    Subject.OTHER: [],
}

_VALID_SUBJECTS = [s.value for s in Subject]
_VALID_CATEGORIES = [c.value for c in Category]


class CreateGenericSubmissionAttrs(ObjectAttrs):
    """Attributes schema for the generic contact submission request."""

    subject = core_fields.String(
        required=True,
        validate=validate.OneOf(_VALID_SUBJECTS, error="Not a valid subject."),
    )
    category = core_fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(_VALID_CATEGORIES, error="Not a valid category."),
    )
    content = core_fields.String(
        required=True,
        validate=validate.Length(min=1, max=3000),
    )
    applicant_full_name = core_fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        validate=validate.Length(min=1, max=300),
    )
    applicant_email = core_fields.Email(
        required=False,
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=254),
    )

    class Meta:
        strict = True
        ordered = True
        object_type = "generic-contact-submission"

    @validates_schema
    def validate_subject_category(self, data: dict, **kwargs) -> None:
        """Enforce the endpoint-level subject × category matrix."""
        subject = Subject(data["subject"])
        category_val = data.get("category")
        allowed = GENERIC_SUBMISSION_ALLOWED_CATEGORIES.get(subject, [])

        if not allowed and category_val:
            raise ValidationError({"category": [_("Category must be empty for this subject.")]})

        if allowed and not category_val:
            raise ValidationError({"category": [_("Category is required for this subject.")]})

        if allowed and category_val and Category(category_val) not in allowed:
            raise ValidationError({"category": [_("Category is not allowed for this subject.")]})


class CreateGenericSubmissionRequest(TopLevel):
    """Top-level JSON:API request schema for POST /submissions/generic."""

    class Meta:
        attrs_schema = CreateGenericSubmissionAttrs
        attrs_schema_required = True
