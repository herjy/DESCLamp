# A few common packages
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# We will use astropy's WCS and ZScaleInterval for plotting
from astropy.wcs import WCS
from astropy.visualization import ZScaleInterval
# Also to convert sky coordinates


# We will use several stack functions
import lsst.geom
import lsst.afw.display as afwDisplay
import lsst.afw.display.rgb as rgb

# And also DESC packages to get the data path
import GCRCatalogs
from GCRCatalogs import GCRQuery
import desc_dc2_dm_data


def catalog_setup(dc2_data_version):
        """ This function fetches catalogs and sets up a butler.
        
        Parameters
        ----------
        dc2_data_version: str
            data version of the catalog. This is used to instantiate the butler.
        """
        # Fetch GCR catalogs
        GCRCatalogs.get_available_catalogs(names_only=True, name_contains=dc2_data_version)
        cat = GCRCatalogs.load_catalog("dc2_object_run"+dc2_data_version)
        
        # Sets up butler
        butler = desc_dc2_dm_data.get_butler(dc2_data_version)
        
        return cat, butler

class Candidates:
    """ Class that handles catalog querries. Fetches postage stamps and light curves of samples of images and allows visualization """
    
    def __init__(self, dc2_data_version):
        
        self.cat, self.butler = catalog_setup(dc2_data_version)

    def catalog_query(self, query, columns = None, tracts = None):
        """ Submits a query and a selection to the catalog. Extract relevant information from catalogs.
        
        Parameters
        ----------
        query: str
            a set of selection criteria to select galaxy objects
        tracts: list
            list of tract numbers. Used to restrict the search to a small number of tracts.
        """
        # The minimum set of infomation needed about objects in the catalog
        
        columns_to_get = ["objectId", "ra", "dec", "tract", "patch"]
        if columns is not None:
            columns_to_get += columns
            columns_to_get = np.unique(columns_to_get)
            
        assert self.cat.has_quantities(columns_to_get)
        
        # Submit the query and get catalog of objects
        if tracts is not None:
            filters = f"(tract == {tracts[0]})"
            for t in tracts[1:]:
                filters +=  f" | (tract == {t})"
        objects = self.cat.get_quantities(columns_to_get, filters=query, native_filters=filters)
        
        # make it a pandas data frame for the ease of manipulation.
        # Objects are nont made attributes of the class in case the use wants postage stamps for a smaller set of objects
        objects = pd.DataFrame(objects)
        return objects

    def make_postage_stamps(self, objects, cutout_size=100, bands = 'irg'):
        """ Extracts a coadd postage stamp of an object from the catalog
        
        Parameters
        ----------
        objects: list of GCR catalog entries
            object to cut a postamp out.
        cutout_size: int
            size of the postage stamp to extract in pixels
        bands: str
            spectral for which patches have to extracted. Default is 'irg'.
        
        """
        skymap = self.butler.get('deepCoadd_skyMap')
        
        cutout_extent = lsst.geom.ExtentI(cutout_size, cutout_size)
        cutouts = {"images":[], "wcs":[], "GCR":[]}
        for (_, object_this) in objects.iterrows():
            radec = lsst.geom.SpherePoint(object_this["ra"], object_this["dec"], lsst.geom.degrees)
            center = skymap.findTract(radec).getWcs().skyToPixel(radec)
            bbox = lsst.geom.BoxI(lsst.geom.Point2I((center.x - cutout_size*0.5, center.y - cutout_size*0.5)), cutout_extent)
        
            cutout = [self.butler.get("deepCoadd_sub", 
                              bbox=bbox, 
                              tract=object_this["tract"], 
                              patch=object_this["patch"], 
                              filter=band
                             ) for band in bands]
            cutouts["images"].append(cutout)
            cutouts["GCR"].append(object_this)
            cutouts["wcs"].append(cutout[0].getWcs().getFitsMetadata())
        
        return cutouts

    def display_cutouts(self, cutouts, cutout_size=100):
        """ Displays RGB image of cutouts on a mosaic
        """
        n = len(cutouts["images"])

        fig = plt.figure(figsize=(36, 36), dpi=100)
        gs = plt.GridSpec(int(np.sqrt(n)+1), int(np.sqrt(n)+1), fig)
        
        for i in range(n):
            image = cutouts["images"][i]
            image_rgb = rgb.makeRGB(*image, dataRange = 2, Q=8)
            del image  # let gc save some memory for us
    
            ax = plt.subplot(gs[i], projection=WCS(cutouts["wcs"][i]), label=str(cutouts["GCR"][i]["objectId"]))
            ax.imshow(image_rgb, origin='lower')
            del image_rgb  # let gc save some memory for us
        
            for c in ax.coords:
                c.set_ticklabel(exclude_overlapping=True, size=10)
                c.set_axislabel('', size=0)
            
        pass
    