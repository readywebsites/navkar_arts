from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Client, Project, QuotationItem, JobCardItem, AddonItem
from urllib.parse import quote
from asgiref.sync import async_to_sync
from playwright.async_api import async_playwright
from django.views.decorators.http import require_POST


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

        if project_id:
            project = get_object_or_404(Project, id=project_id)

        if project:
            client = project.client
            client.name = client_name
            client.address = client_address
            client.phone = client_phone
            client.save()
            
            project.site_address = site_address
            project.save()
        else:
            client, _ = Client.objects.update_or_create(
                phone=client_phone,
                defaults={'name': client_name, 'address': client_address}
            )
            project = Project.objects.create(client=client, site_address=site_address)

        # ================= QUOTATION + JOB CARD =================

        quotation_item_ids = request.POST.getlist('quotation_item_id[]')
        job_card_item_ids = request.POST.getlist('job_card_item_id[]')
        descriptions = request.POST.getlist('quotation_description[]')
        qtys = request.POST.getlist('quotation_qty[]')
        rates = request.POST.getlist('quotation_rate[]')
        discounts = request.POST.getlist('quotation_discount_percent[]')
        
        heights = request.POST.getlist('height[]')
        widths = request.POST.getlist('width[]')
        parts = request.POST.getlist('part[]')
        company_names = request.POST.getlist('company_name[]')
        booklet_nos = request.POST.getlist('booklet_no[]')
        page_nos = request.POST.getlist('page_no[]')
        reference_images = request.FILES.getlist('reference_image[]')

        processed_quotation_ids = []
        processed_job_card_ids = []

        for i in range(len(descriptions)):
            if descriptions[i]:
                quotation_item_id = quotation_item_ids[i] if i < len(quotation_item_ids) else None
                job_card_item_id = job_card_item_ids[i] if i < len(job_card_item_ids) else None

                # Quotation Item
                if quotation_item_id:
                    quotation_item = QuotationItem.objects.get(id=quotation_item_id, project=project)
                    quotation_item.description = descriptions[i]
                    quotation_item.quantity = float(qtys[i] or 0)
                    quotation_item.rate = float(rates[i] or 0)
                    quotation_item.discount_percent = float(discounts[i] or 0)
                    quotation_item.save()
                    processed_quotation_ids.append(quotation_item.id)
                else:
                    quotation_item = QuotationItem.objects.create(
                        project=project,
                        description=descriptions[i],
                        quantity=float(qtys[i] or 0),
                        rate=float(rates[i] or 0),
                        discount_percent=float(discounts[i] or 0)
                    )

                # Job Card Item
                if job_card_item_id:
                    job_card_item = JobCardItem.objects.get(id=job_card_item_id, project=project)
                    job_card_item.height = float(heights[i] or 0)
                    job_card_item.width = float(widths[i] or 0)
                    job_card_item.part = float(parts[i] or 0)
                    job_card_item.company_name = company_names[i]
                    job_card_item.booklet_no = booklet_nos[i]
                    job_card_item.page_no = page_nos[i]
                    if i < len(reference_images) and reference_images[i]:
                        job_card_item.reference_image = reference_images[i]
                    job_card_item.save()
                    processed_job_card_ids.append(job_card_item.id)
                else:
                    JobCardItem.objects.create(
                        project=project,
                        height=float(heights[i] or 0),
                        width=float(widths[i] or 0),
                        part=float(parts[i] or 0),
                        company_name=company_names[i],
                        booklet_no=booklet_nos[i],
                        page_no=page_nos[i],
                        reference_image=reference_images[i] if i < len(reference_images) else None
                    )

        # Delete items that were removed from the form
        if project_id:
            project.quotation_items.exclude(id__in=processed_quotation_ids).delete()
            project.job_card_items.exclude(id__in=processed_job_card_ids).delete()

        # ================= ADD-ONS =================

        addon_item_ids = request.POST.getlist('addon_item_id[]')
        addon_descriptions = request.POST.getlist('addon_description[]')
        addon_rfts = request.POST.getlist('addon_rft_sqft[]')
        addon_rates = request.POST.getlist('addon_rate[]')
        addon_remarks = request.POST.getlist('addon_remarks[]')
        
        processed_addon_ids = []

        for i in range(len(addon_descriptions)):
            if addon_descriptions[i] and addon_rfts[i] and addon_rates[i]:
                addon_item_id = addon_item_ids[i] if i < len(addon_item_ids) else None
                if addon_item_id:
                    addon_item = AddonItem.objects.get(id=addon_item_id, project=project)
                    addon_item.description = addon_descriptions[i]
                    addon_item.rft_sqft = float(addon_rfts[i] or 0)
                    addon_item.rate = float(addon_rates[i] or 0)
                    addon_item.remarks = addon_remarks[i]
                    addon_item.save()
                    processed_addon_ids.append(addon_item.id)
                else:
                    AddonItem.objects.create(
                        project=project,
                        description=addon_descriptions[i],
                        rft_sqft=float(addon_rfts[i] or 0),
                        rate=float(addon_rates[i] or 0),
                        remarks=addon_remarks[i]
                    )

        if project_id:
            project.addon_items.exclude(id__in=processed_addon_ids).delete()

        return redirect('generator:project_detail', project_id=project.id)

    context = {
        'project': project
    }
    if project:
        context['date'] = project.date
        quotation_items = project.quotation_items.all()
        job_card_items = project.job_card_items.all()
        
        num_items = max(len(quotation_items), len(job_card_items))
        
        context['combined_items'] = list(zip(list(quotation_items) + [None]*num_items, list(job_card_items) + [None]*num_items))[:num_items]

    return render(request, 'generator/home.html', context)


# ================= PROJECT LIST =================

def project_list_view(request):
    projects = Project.objects.all().order_by('-id')
    return render(request, 'generator/project_list.html', {'projects': projects})

# ================= DELETE PROJECT =================

@require_POST
def delete_project_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project.delete()
    return redirect('generator:project_list')


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
    
    addons = project.addon_items.all()
    addons_total = sum(addon.amount for addon in addons)

    html = render_to_string('generator/quotation_pdf.html', {
        'project': project,
        'items': items,
        'addons': addons,
        'items_total': total_amount,
        'addons_total': addons_total,
        'grand_total': total_amount + addons_total,
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