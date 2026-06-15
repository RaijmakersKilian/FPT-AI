"""
Gedeelde visualisatie-hulpfuncties.
Gebruik show_windows() voor meerdere Open3D vensters tegelijk.
"""
import numpy as np


def color_cloud(pcd, fallback_color):
    """
    Geef de cloud een uniforme kleur ALLEEN als hij geen originele kleuren heeft.
    IFC heeft nooit kleuren → krijgt altijd fallback_color (blauw).
    MASt3R heeft scan-kleuren → blijft ongewijzigd.
    """
    if not pcd.has_colors():
        pcd.paint_uniform_color(fallback_color)
    return pcd


def show_windows(*window_specs, point_size=2.0):
    """
    Open meerdere Open3D vensters tegelijk in dezelfde thread via een polling loop.

    window_specs: lijst van (geometrieën, titel) tuples
    Voorbeeld:
        show_windows(
            ([pcd1, pcd2], "Venster 1 — overzicht"),
            ([pcd3],       "Venster 2 — coverage"),
        )
    """
    import open3d as o3d

    # Onderdruk Open3D WARNING-berichten (bijv. SetViewPoint venster nog niet klaar)
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)

    visualizers = []
    for geoms, title in window_specs:
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name=title, width=1280, height=800)
        for g in geoms:
            vis.add_geometry(g)
        opt = vis.get_render_option()
        opt.point_size = point_size
        opt.background_color = np.array([0.08, 0.08, 0.08])
        # Meerdere poll-rondes zodat het venster volledig klaar is voor reset_view_point
        for _ in range(10):
            vis.poll_events()
            vis.update_renderer()
        vis.reset_view_point(True)
        visualizers.append(vis)

    # Poll alle vensters tegelijk in één loop — beide blijven interactief
    while True:
        still_open = [vis.poll_events() for vis in visualizers]
        for vis in visualizers:
            vis.update_renderer()
        if not all(still_open):
            break

    for vis in visualizers:
        vis.destroy_window()
