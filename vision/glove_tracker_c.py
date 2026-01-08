import cv2
import numpy as np

class GloveFeatures:
    def __init__(self, mask=None, contour=None, center=None, fingertips=None, roi=None, roi_offset=(0,0)):
        self.mask = mask
        self.contour = contour
        self.center = center
        self.fingertips = fingertips or []
        self.roi = roi
        self.roi_offset = roi_offset  # (x0,y0) of roi in full frame

class SegmenterBase:
    """方案C预留：轻量分割模型接口（stub）。"""
    def segment(self, bgr_roi: np.ndarray):
        return None  # return binary mask or None

class GloveTrackerC:
    def __init__(self, hsv_lower=(20,80,80), hsv_upper=(40,255,255), erode=1, dilate=2, min_area=1500, segmenter=None):
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
        self.erode = int(erode)
        self.dilate = int(dilate)
        self.min_area = int(min_area)
        self.segmenter = segmenter or SegmenterBase()

    def update_hsv(self, lower, upper):
        self.hsv_lower = np.array(lower, dtype=np.uint8)
        self.hsv_upper = np.array(upper, dtype=np.uint8)

    def _hsv_mask(self, frame_bgr):
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        if self.erode > 0:
            mask = cv2.erode(mask, None, iterations=self.erode)
        if self.dilate > 0:
            mask = cv2.dilate(mask, None, iterations=self.dilate)
        return mask

    def process(self, frame_bgr):
        # 1) HSV mask on full frame
        mask = self._hsv_mask(frame_bgr)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return GloveFeatures(mask=mask)

        cnt = max(cnts, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < self.min_area:
            return GloveFeatures(mask=mask)

        # 2) ROI by bounding rect for optional segmenter
        x, y, w, h = cv2.boundingRect(cnt)
        pad = 12
        x0 = max(0, x - pad); y0 = max(0, y - pad)
        x1 = min(frame_bgr.shape[1], x + w + pad); y1 = min(frame_bgr.shape[0], y + h + pad)
        roi = frame_bgr[y0:y1, x0:x1]

        # 3) optional segmenter refine (stub returns None now)
        seg = self.segmenter.segment(roi)
        if seg is not None:
            # seg expected 0/255 mask in ROI coords
            mask_roi = seg.astype(np.uint8)
            cnts2, _ = cv2.findContours(mask_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts2:
                cnt_roi = max(cnts2, key=cv2.contourArea)
                cnt = cnt_roi + np.array([[[x0, y0]]], dtype=np.int32)

        # 4) center
        M = cv2.moments(cnt)
        center = None
        if M["m00"] > 1e-6:
            center = (int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]))

        # 5) fingertips from hull (rough)
        fingertips = []
        hull = cv2.convexHull(cnt, returnPoints=True)
        if hull is not None and len(hull) > 5:
            pts = hull[:, 0, :]
            pts_sorted = pts[np.argsort(pts[:, 1])]
            top = pts_sorted[:12]
            for p in top:
                if all(np.linalg.norm(p - np.array(q)) > 25 for q in fingertips):
                    fingertips.append((int(p[0]), int(p[1])))
            fingertips = fingertips[:5]

        return GloveFeatures(mask=mask, contour=cnt, center=center, fingertips=fingertips, roi=roi, roi_offset=(x0,y0))