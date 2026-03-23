from django.contrib import admin
from .models import Client, Project, QuotationItem, JobCardItem

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

class JobCardItemInline(admin.TabularInline):
    model = JobCardItem
    extra = 1

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    search_fields = ('name', 'phone')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('client', 'site_address', 'date')
    list_filter = ('date', 'client')
    inlines = [QuotationItemInline, JobCardItemInline]

@admin.register(QuotationItem)
class QuotationItemAdmin(admin.ModelAdmin):
    list_display = ('project', 'description', 'quantity', 'rate', 'final_amount')
    list_filter = ('project__client',)

@admin.register(JobCardItem)
class JobCardItemAdmin(admin.ModelAdmin):
    list_display = ('project', 'company_name', 'booklet_no', 'page_no')
    list_filter = ('project__client',)