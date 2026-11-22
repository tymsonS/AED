# AEDane: demo wykazu zbiorczego AED na lokalnym portalu (README-DOCKER-AED.md, „Demo”).
#
# Uruchamia go aed_demo.sh w kontenerze panelu:
#   docker exec -i mcod-admin python manage.py shell < aed_demo_wykaz.py
#
# Co robi (można powtarzać – poprzednie dane demo są usuwane):
#   1. kategoria HEAL („Zdrowie”) – dane startowe portalu mają tylko AGRI;
#   2. dla każdego pliku media/aed-demo/<gmina>.csv (pakiety z ingest/): instytucja dysponenta,
#      zbiór z kategorią HEAL i zasób CSV z flagą „Zawiera wykaz defibrylatorów AED”;
#   3. czeka na walidację portalu (plik, dane, link);
#   4. uruchamia zadanie wykazu zbiorczego (#58) i wypisuje wynik.
#
# Plik wykonuje `manage.py shell` przez exec() – cały kod jest w main(), żeby funkcje
# pomocnicze widziały importy.


def main():
    import csv
    import datetime
    import io
    import time
    import uuid
    from collections import Counter
    from pathlib import Path

    from django.apps import apps
    from django.conf import settings
    from django.core.files.uploadedfile import SimpleUploadedFile

    from mcod.resources.tasks.aed import create_main_aed_resource_task

    Category = apps.get_model("categories", "Category")
    Organization = apps.get_model("organizations", "Organization")
    Dataset = apps.get_model("datasets", "Dataset")
    Resource = apps.get_model("resources", "Resource")
    ResourceFile = apps.get_model("resources", "ResourceFile")
    AggregatedAEDInfo = apps.get_model("resources", "AggregatedAEDInfo")

    demo_dir = Path(settings.MEDIA_ROOT) / "aed-demo"
    # Plik -> (instytucja, slug instytucji, nazwa gminy w tytule zbioru).
    providers = {
        "krosno.csv": ("Urząd Miasta Krosna", "urzad-miasta-krosna", "Krosno"),
        "przemysl.csv": ("Urząd Miejski w Przemyślu", "urzad-miejski-w-przemyslu", "Przemyśl"),
        "marki.csv": ("Urząd Miasta Marki", "urzad-miasta-marki", "Marki"),
    }
    template_org_pk = 2838  # „Pierwsza instytucja” z danych startowych (init_mcod_db)
    dataset_prefix = "Lokalizacje defibrylatorów AED – "

    files = [demo_dir / name for name in providers if (demo_dir / name).exists()]
    if not files:
        print(f"Brak plików w {demo_dir} – uruchom aed_demo.sh")
        return

    heal, _ = Category.objects.get_or_create(code="HEAL", defaults={"title": "Zdrowie", "status": "published"})

    def institution(title, slug):
        org = Organization.objects.filter(slug=slug).first()
        if org:
            return org
        org = Organization.objects.get(pk=template_org_pk)
        org.pk = org.id = None
        org.uuid = uuid.uuid4()
        org.title, org.slug, org.institution_type = title, slug, "local"
        org.save()
        return org

    # Poprzednie dane demo – tylko zbiory instytucji demo i wykaz zbiorczy instytucji-właściciela
    # z ustawień, żeby nie skasować zbioru o podobnym tytule dodanego ręcznie (review #67).
    demo_slugs = [slug for _, slug, _ in providers.values()]
    old = list(
        Dataset.raw.filter(title__startswith=dataset_prefix, organization__slug__in=demo_slugs)
        .values_list("pk", flat=True)
    ) + list(
        Dataset.raw.filter(
            title=settings.MAIN_AED_DATASET_DEFAULT_TITLE,
            organization_id=settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK,
        ).values_list("pk", flat=True)
    )
    AggregatedAEDInfo.objects.all().delete()
    Resource.raw.filter(dataset_id__in=old).delete()
    Dataset.raw.filter(pk__in=old).delete()
    print(f"Usunięte poprzednie zbiory demo: {len(old)}")

    created = []
    for path in files:
        title, slug, municipality = providers[path.name]
        org = institution(title, slug)
        dataset = Dataset.objects.create(
            title=dataset_prefix + municipality,
            notes=f"AED w gminie {municipality} – pakiet dostawcy z ingest/ (AEDane, demo wykazu zbiorczego).",
            organization=org,
            has_dynamic_data=False,
            has_high_value_data=False,
            has_high_value_data_from_ec_list=False,
            has_research_data=False,
            update_frequency="yearly",
            status="published",
        )
        dataset.categories.set([heal])
        dataset.save()
        resource = Resource.objects.create(
            title=f"AED – {municipality} (CSV)",
            description="Wzorcowy zakres danych AED v0.2.",
            dataset=dataset,
            has_dynamic_data=False,
            has_high_value_data=False,
            has_high_value_data_from_ec_list=False,
            has_research_data=False,
            contains_aed_data=True,
            status="published",
            data_date=datetime.date.today(),
        )
        upload = SimpleUploadedFile(name=f"aed-{path.stem}.csv", content=path.read_bytes(), content_type="text/csv")
        ResourceFile.objects.create(resource=resource, is_main=True, file=upload)
        created.append(resource.pk)
        print(f"{municipality}: instytucja {org.pk}, zbiór {dataset.pk}, zasób {resource.pk}")

    def statuses(pk):
        r = Resource.raw.get(pk=pk)
        return r.file_tasks_last_status, r.data_tasks_last_status, r.link_tasks_last_status

    print("Czekam na walidację portalu (celery)…")
    deadline = time.time() + 300
    while time.time() < deadline:
        current = {pk: statuses(pk) for pk in created}
        if all(s in ("SUCCESS", "FAILURE") for st in current.values() for s in st):
            break
        time.sleep(5)
    for pk, st in current.items():
        print(f"  zasób {pk}: plik {st[0]}, dane {st[1]}, link {st[2]}")
    if any(s != "SUCCESS" for st in current.values() for s in st):
        print("Nie wszystkie zasoby przeszły walidację – wykaz weźmie tylko poprawne (logi: docker logs mcod-celery).")

    result = create_main_aed_resource_task.apply()
    print(f"Zadanie wykazu: {result.status}")
    info = AggregatedAEDInfo.objects.last()
    if not info or not info.resource:
        print("Wykaz nie powstał.")
        return
    wykaz = info.resource
    rows = list(csv.DictReader(io.StringIO(Path(wykaz.main_file.path).read_text(encoding="utf-8"))))
    print(f"Wykaz zbiorczy: zbiór {wykaz.dataset.pk}, zasób {wykaz.pk} – {len(rows)} AED")
    for name, count in sorted(Counter(r["instytucja_publikujaca"] for r in rows).items()):
        print(f"  {name}: {count}")
    for r in rows:
        if r["mozliwy_duplikat"]:
            print(f"  możliwy duplikat: {r['instytucja_publikujaca']} – {r['nazwa_obiektu']} ({r['miejscowosc']})")


main()
