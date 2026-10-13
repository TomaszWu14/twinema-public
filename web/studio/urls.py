from django.urls import path

from . import api, views

app_name = "studio"

urlpatterns = [
    path("studio/<int:pk>/render/", views.render_shots, name="render_shots"),
    path("studio/<int:pk>/montaz/", views.montage_create, name="montage_create"),
    path("studio/<int:pk>/status.json", views.status_json, name="status_json"),
    path("studio/film/<int:pk>.mp4", views.film_file, name="film_file"),
    path("studio/<int:pk>/deck.pdf", views.deck_pdf, name="deck_pdf"),
    path("api/studio/montage/claim/", api.claim, name="api_claim"),
    path("api/studio/montage/<int:pk>/clip/<int:n>/", api.clip, name="api_clip"),
    path("api/studio/montage/<int:pk>/result/", api.result, name="api_result"),
    path("api/studio/montage/<int:pk>/fail/", api.fail, name="api_fail"),
    path("studio/", views.presentation_list, name="list"),
    path("studio/nowa/", views.presentation_create, name="create"),
    path("studio/<int:pk>/", views.presentation_detail, name="detail"),
    path("studio/<int:pk>/kwestie/", views.shots_save, name="shots_save"),
    path("studio/<int:pk>/szkic-ai/", views.shots_ai, name="shots_ai"),
    path("studio/<int:pk>/szkic-szablon/", views.shots_template, name="shots_template"),
    path("studio/<int:pk>/zatwierdz/", views.approve, name="approve"),
    path("studio/<int:pk>/edycja/", views.reopen, name="reopen"),
    path("studio/<int:pk>/usun/", views.presentation_delete, name="delete"),
    path("studio/<int:pk>/napisy.srt", views.subtitles, name="subtitles"),
    path("studio/<int:pk>/youtube.txt", views.youtube_text, name="youtube"),
]
