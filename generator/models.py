from django.db import models
from django.utils import timezone

class Client(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.name

class Project(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    site_address = models.TextField()
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Project for {self.client.name} at {self.site_address}"

class QuotationItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='quotation_items')
    description = models.CharField(max_length=255)
    quantity = models.FloatField()
    rate = models.FloatField()
    discount_percent = models.FloatField(default=0)

    @property
    def total(self):
        return self.quantity * self.rate

    @property
    def discount_amount(self):
        return self.total * (self.discount_percent / 100)

    @property
    def final_amount(self):
        return self.total - self.discount_amount

    def __str__(self):
        return self.description

class JobCardItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='job_card_items')
    company_name = models.CharField(max_length=100)
    booklet_no = models.CharField(max_length=50)
    page_no = models.CharField(max_length=50)
    reference_image = models.ImageField(upload_to='job_card_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.company_name} - Booklet {self.booklet_no}, Page {self.page_no}"

class AddonItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='addon_items')
    description = models.CharField(max_length=255)
    rft_sqft = models.FloatField()
    rate = models.FloatField()
    remarks = models.TextField(blank=True, null=True)

    @property
    def amount(self):
        return self.rft_sqft * self.rate

    def __str__(self):
        return self.description