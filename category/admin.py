from django.contrib import admin
from .models import Category
# Register your models here.
from django.contrib import admin
from django.db import connection
from .models import Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['category_name', 'slug']
    prepopulated_fields = {'slug': ('category_name',)}

    def delete_queryset(self, request, queryset):
        """Handle bulk delete from admin"""
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        for category in queryset:
            cat_id = category.id
            cursor.execute(f"DELETE FROM carts_cartitem WHERE product_id IN (SELECT id FROM store_product WHERE category_id={cat_id});")
            cursor.execute(f"DELETE FROM carts_cartitem WHERE product_id IN (SELECT id FROM product_product WHERE category_id={cat_id});")
            cursor.execute(f"DELETE FROM store_product WHERE category_id={cat_id};")
            cursor.execute(f"DELETE FROM product_product WHERE category_id={cat_id};")
        
        queryset.delete()
        cursor.execute("PRAGMA foreign_keys=ON;")

    def delete_model(self, request, obj):
        """Handle single delete from admin"""
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        cat_id = obj.id
        cursor.execute(f"DELETE FROM carts_cartitem WHERE product_id IN (SELECT id FROM store_product WHERE category_id={cat_id});")
        cursor.execute(f"DELETE FROM carts_cartitem WHERE product_id IN (SELECT id FROM product_product WHERE category_id={cat_id});")
        cursor.execute(f"DELETE FROM store_product WHERE category_id={cat_id};")
        cursor.execute(f"DELETE FROM product_product WHERE category_id={cat_id};")
        
        obj.delete()
        cursor.execute("PRAGMA foreign_keys=ON;")

class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug':('category_name',)}


