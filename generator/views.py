from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Client, Project, QuotationItem, JobCardItem, AddonItem
from urllib.parse import quote
from asgiref.sync import async_to_sync
from playwright.async_api import async_playwright


# ================= HOME =================

def home_view(request, project_id=None):
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id)

    if request.method == 'POST':
        client_name = request.POST.get('client_name')
        client_address = request.POST.get('client_address')
        client_phone = request.POST.get('client_phone')
        site_address = request.POST.get('site_address')

        # If we are editing, fetch the existing project. Otherwise, create a new one.
        if project:
            client = project.client
            client.name = client_name
            client.address = client_address
            client.phone = client_phone
            client.save()
            
            project.site_address = site_address
            project.save()

            # Clear old items before saving new ones
            project.quotation_items.all().delete()
            project.job_card_items.all().delete()
            project.addon_items.all().delete()
        else:
            # Use update_or_create for cleaner client handling
            client, _ = Client.objects.update_or_create(
                phone=client_phone,
                defaults={'name': client_name, 'address': client_address}
            )

            project = Project.objects.create(client=client, site_address=site_address)

        # ================= QUOTATION + JOB CARD =================

        descriptions = request.POST.getlist('quotation_description[]')
        qtys = request.POST.getlist('quotation_qty[]')
        rates = request.POST.getlist('quotation_rate[]')
        discounts = request.POST.getlist('quotation_discount_percent[]')
        
        heights = request.POST.getlist('height[]')
        widths = request.POST.getlist('width[]')
        parts = request.POST.getlist('part[]')

        for i in range(len(descriptions)):
            if descriptions[i]:
                # Quotation
                QuotationItem.objects.create(
                    project=project,
                    description=descriptions[i],
                    quantity=float(qtys[i] or 0),
                    rate=float(rates[i] or 0),
                    discount_percent=float(discounts[i] or 0)
                )

                # Job Card (auto)
                JobCardItem.objects.create(
                    project=project,
                    company_name=request.POST.get(f'company_name_{i}', ''),
                    booklet_no=request.POST.get(f'booklet_no_{i}', ''),
                    page_no=request.POST.get(f'page_no_{i}', ''),
                    height=float(heights[i] or 0),
                    width=float(widths[i] or 0),
                    part=float(parts[i] or 0),
                    reference_image=request.FILES.get(f'reference_image_{i}')
                )
        
        # ================= ADD-ONS =================

        addon_descriptions = request.POST.getlist('addon_description[]')
        addon_rfts = request.POST.getlist('addon_rft_sqft[]')
        addon_rates = request.POST.getlist('addon_rate[]')
        addon_remarks = request.POST.getlist('addon_remarks[]')

        for i in range(len(addon_descriptions)):
            if addon_descriptions[i] and addon_rfts[i] and addon_rates[i]:
                AddonItem.objects.create(
                    project=project,
                    description=addon_descriptions[i],
                    rft_sqft=float(addon_rfts[i] or 0),
                    rate=float(addon_rates[i] or 0),
                    remarks=addon_remarks[i]
                )

        return redirect('generator:project_detail', project_id=project.id)

    # Prepare context for template
    context = {
        'project': project
    }
    if project:
        context['date'] = project.date
        # Pre-zip the items for easier iteration in the template
        quotation_items = project.quotation_items.all()
        job_card_items = project.job_card_items.all()
        
        # Ensure we have a matching item for each, even if empty
        num_items = max(len(quotation_items), len(job_card_items))
        
        context['combined_items'] = list(zip(list(quotation_items) + [None]*num_items, list(job_card_items) + [None]*num_items))[:num_items]

    return render(request, 'generator/home.html', context)


# ================= PROJECT LIST =================

def project_list_view(request):
    projects = Project.objects.all().order_by('-id')
    return render(request, 'generator/project_list.html', {'projects': projects})


# ================= PROJECT DETAIL =================

def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    quotation_pdf_url = reverse('generator:quotation_pdf', args=[project.id])
    job_card_pdf_url = reverse('generator:job_card_pdf', args=[project.id])

    public_quotation_url = request.build_absolute_uri(quotation_pdf_url)
    whatsapp_message = f"Your quotation is ready: {public_quotation_url}"
    whatsapp_url = f"https://wa.me/{project.client.phone}?text={quote(whatsapp_message)}"

    return render(request, 'generator/project_view.html', {
        'project': project,
        'quotation_pdf_url': quotation_pdf_url,
        'job_card_pdf_url': job_card_pdf_url,
        'whatsapp_url': whatsapp_url,
    })


# ================= PLAYWRIGHT HELPER =================

async def _generate_pdf_from_html(base_url, html_content):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        base_tag = f'<base href="{base_url}">'
        html_content = html_content.replace('<head>', f'<head>{base_tag}', 1)

        await page.set_content(html_content)

        pdf = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '1cm', 'bottom': '1cm', 'left': '1cm', 'right': '1cm'}
        )

        await browser.close()
    return pdf


# ================= QUOTATION PDF =================

def generate_quotation_pdf(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    items = project.quotation_items.all()
    total_amount = sum(item.final_amount for item in items)

    html = render_to_string('generator/quotation_pdf.html', {
        'project': project,
        'items': items,
        'total_amount': total_amount
    })

    base_url = request.build_absolute_uri('/')

    pdf_bytes = async_to_sync(_generate_pdf_from_html)(base_url, html)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="quotation_{project.id}.pdf"'
    return response


# ================= JOB CARD PDF =================

def generate_job_card_pdf(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    html = render_to_string('generator/job_card_pdf.html', {
        'project': project,
        'items': project.job_card_items.all()
    })

    base_url = request.build_absolute_uri('/')

    pdf_bytes = async_to_sync(_generate_pdf_from_html)(base_url, html)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="job_card_{project.id}.pdf"'
    return response