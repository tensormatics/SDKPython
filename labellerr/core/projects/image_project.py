from .projects import LabellerrProject, LabellerrProjectMeta

class ImageProject(LabellerrProject):
    def fetch_datasets(self):
        print ("Yo I am gonna fetch some datasets!")

LabellerrProjectMeta.register('image', ImageProject)
