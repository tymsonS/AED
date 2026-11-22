import factory
from django.utils import timezone

from mcod.submissions.models import Category, Subject, SubmissionEvent


class SubmissionEventFactory(factory.django.DjangoModelFactory):
    subject = Subject.DATA.value
    category = Category.SHARING.value
    submission_date = factory.LazyFunction(timezone.now)

    class Meta:
        model = SubmissionEvent
