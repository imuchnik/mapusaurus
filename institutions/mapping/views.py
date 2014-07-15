from django.shortcuts import render

from respondants.models import Institution


def home(request):
    """Display the map. If lender info is present, provide it to the
    template"""
    lender = request.GET.get('lender', '')
    context = {}
    if lender and len(lender) > 1 and lender[0].isdigit():
        query = Institution.objects.filter(agency_id=int(lender[0]))
        query = query.filter(ffiec_id=lender[1:])
        query = query.select_related('agency', 'zip_code')
        lender = query.first()
        if lender:
            context['lender'] = lender

    return render(request, 'index.html', context)
