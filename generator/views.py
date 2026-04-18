from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Client, Project, QuotationItem, JobCardItem
from django.conf import settings
from urllib.parse import quote
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

# --- Form and Project Views (Synchronous) ---

def home_view(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name')
        client_address = request.POST.get('client_address')
        client_phone = request.POST.get('client_phone')
        site_address = request.POST.get('site_address')

        print(f"Client Name: {client_name}, Phone: {client_phone}, Address: {client_address}")
        print(f"Site Address: {site_address}")

        client, _ = Client.objects.get_or_create(phone=client_phone, defaults={'name': client_name, 'address': client_address})
        project = Project.objects.create(client=client, site_address=site_address)

        # Process Quotation Items
        quotation_descriptions = request.POST.getlist('quotation_description[]')
        quotation_quantities = request.POST.getlist('quotation_qty[]')
        quotation_rates = request.POST.getlist('quotation_rate[]')
        quotation_discounts = request.POST.getlist('quotation_discount_percent[]')

        print(f"Quotation Descriptions: {quotation_descriptions}")
        print(f"Quotation Quantities: {quotation_quantities}")

        for i in range(len(quotation_descriptions)):
            if quotation_descriptions[i]:
                QuotationItem.objects.create(
                    project=project,
                    description=quotation_descriptions[i],
                    quantity=float(quotation_quantities[i] or 0),
                    rate=float(quotation_rates[i] or 0),
                    discount_percent=float(quotation_discounts[i] or 0)
                )

        # Process Job Card Items
        # Collect all submitted job card data into a list of dictionaries
        job_card_data = []
        i = 0
        while True:
            company_name_key = f'job_card_company_name_{i}'
            if company_name_key in request.POST:
                company_name = request.POST.get(company_name_key)
                booklet_no = request.POST.get(f'job_card_booklet_no_{i}')
                page_no = request.POST.get(f'job_card_page_no_{i}')
                image = request.FILES.get(f'job_card_image_{i}') # Use .get() to safely retrieve image

                if company_name: # Only create item if company name is provided
                    job_card_data.append({
                        'company_name': company_name,
                        'booklet_no': booklet_no,
                        'page_no': page_no,
                        'reference_image': image
                    })
                i += 1
            else:
                break # No more job card entries

        for item_data in job_card_data:
            JobCardItem.objects.create(
                project=project,
                company_name=item_data['company_name'],
                booklet_no=item_data['booklet_no'],
                page_no=item_data['page_no'],
                reference_image=item_data['reference_image']
            )
        
        return redirect('generator:project_list')

    return render(request, 'generator/home.html')

def project_list_view(request):
    projects = Project.objects.all().order_by('-id') # Order by id descending to show newest first
    context = {
        'projects': projects
    }
    return render(request, 'generator/project_list.html', context)

def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    quotation_pdf_url = reverse('generator:quotation_pdf', args=[project.id])
    job_card_pdf_url = reverse('generator:job_card_pdf', args=[project.id])

    public_quotation_url = request.build_absolute_uri(quotation_pdf_url)
    whatsapp_message = f"Your quotation is ready: {public_quotation_url}"
    whatsapp_url = f"https://wa.me/{project.client.phone}?text={quote(whatsapp_message)}"

    context = {
        'project': project,
        'quotation_pdf_url': quotation_pdf_url,
        'job_card_pdf_url': job_card_pdf_url,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'generator/project_view.html', context)

# --- PDF Generation (Async Helper and Sync Views) ---

async def _generate_pdf_from_html(base_url, html_content):
    """Async helper to generate PDF from HTML using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Inject a <base> tag into the HTML to handle relative paths for images/css
        base_tag = f'<base href="{base_url}">'
        html_with_base = html_content.replace('<head>', f'<head>{base_tag}', 1)

        await page.set_content(html_with_base)
        
        pdf_bytes = await page.pdf(format='A4', print_background=True, margin={'top': '1cm', 'bottom': '1cm', 'left': '1cm', 'right': '1cm'})
        await browser.close()
    return pdf_bytes

async def generate_quotation_pdf(request, project_id):
    """Asynchronous view to generate the quotation PDF."""
    project = get_object_or_404(Project, id=project_id)
    items = project.quotation_items.all()
    total_amount = sum(item.final_amount for item in items)
    
    html_string = render_to_string('generator/quotation_pdf.html', {
        'project': project,
        'items': items,
        'total_amount': total_amount
    })

    base_url = request.build_absolute_uri('/')
    pdf_bytes = await _generate_pdf_from_html(base_url, html_string)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="quotation_{project.id}.pdf"'
    return response

async def generate_job_card_pdf(request, project_id):
    """Asynchronous view to generate the job card PDF."""
    project = get_object_or_404(Project, id=project_id)
    
    html_string = render_to_string('generator/job_card_pdf.html', {
        'project': project,
        'items': project.job_card_items.all()
    })

    base_url = request.build_absolute_uri('/')
    pdf_bytes = await _generate_pdf_from_html(base_url, html_string)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="job_card_{project.id}.pdf"'
    return response
