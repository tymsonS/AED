from mcod.core.api import fields
from mcod.core.api.jsonapi.serializers import ObjectAttrs, TopLevel


class GenericSubmissionAttrs(ObjectAttrs):
    message = fields.Str(required=True)

    class Meta:
        object_type = "generic-contact-submission"
        url_template = "{api_url}/submissions/generic"


class GenericSubmissionApiResponse(TopLevel):
    class Meta:
        attrs_schema = GenericSubmissionAttrs
