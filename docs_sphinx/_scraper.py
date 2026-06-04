from sphinx_gallery.scrapers import figure_rst


class ReprScraper:
    """Capture objects whose last repr is _repr_png_ or _repr_svg_."""

    def __repr__(self):
        return "ReprScraper"

    def __call__(self, block, block_vars, gallery_conf):
        obj = block_vars["example_globals"].get("___")
        if obj is None:
            return ""
        image_path_iterator = block_vars["image_path_iterator"]
        image_paths = []
        if hasattr(obj, "_repr_png_"):
            path = next(image_path_iterator)
            with open(path, "wb") as f:
                f.write(obj._repr_png_())
            image_paths.append(path)
        elif hasattr(obj, "_repr_image_png"):
            path = next(image_path_iterator)
            with open(path, "wb") as f:
                f.write(obj._repr_image_png())
            image_paths.append(path)
        elif hasattr(obj, "_repr_svg_"):
            path = next(image_path_iterator).replace(".png", ".svg")
            with open(path, "w") as f:
                f.write(obj._repr_svg_())
            image_paths.append(path)
        if not image_paths:
            return ""
        return figure_rst(image_paths, gallery_conf["src_dir"])
