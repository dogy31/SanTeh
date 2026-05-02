from django.contrib import admin
from .models import Profile, Request, Photo, WorkerInstruction

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone')
    search_fields = ('user__username', 'user__first_name', 'phone')


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ('photo_type', 'image', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    exclude = ('client_email',)
    list_display = ('id', 'client_name', 'client_phone', 'client_phone_2', 'client_address', 'status', 'created_date', 'assigned_to')
    list_filter = ('status', 'assigned_to')
    search_fields = ('id', 'client_name', 'client_phone', 'client_phone_2', 'client_address', 'description', 'parts__name')
    inlines = (PhotoInline,)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'photo_type', 'uploaded_at')
    list_filter = ('photo_type',)


@admin.register(WorkerInstruction)
class WorkerInstructionAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at')