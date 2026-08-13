/* One image from the device library, normalised for uploadMedia. Wraps
   expo-image-picker so screens never touch its API shape directly — the
   permission ask, the cancel case and the name/type fallbacks live here once.

   Returns null when the person cancels OR when permission is denied; the
   caller treats both as "nothing chosen" rather than as an error, because
   neither is one. quality 0.8 keeps a phone photo well under the API's image
   size ceiling without visible loss on a card-sized render. */
import * as ImagePicker from "expo-image-picker";
import type { LocalImage } from "./api";

function toLocalImage(asset: ImagePicker.ImagePickerAsset): LocalImage {
  /* fileName and mimeType are optional on the asset (Android in particular
     omits them); the uri extension and a jpeg default are honest fallbacks —
     the backend validates the real content type server-side. */
  const name = asset.fileName ?? asset.uri.split("/").pop() ?? "photo.jpg";
  const type = asset.mimeType ?? (name.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg");
  return { uri: asset.uri, name, type };
}

export async function pickImage(): Promise<LocalImage | null> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) return null;

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.8,
  });
  if (result.canceled || result.assets.length === 0) return null;
  return toLocalImage(result.assets[0]);
}

/* Several images in one trip to the gallery — what a portfolio actually
   needs, where picking eight photos one at a time is eight permission checks
   and eight round trips. Returns [] for cancel or denial, the same contract
   as pickImage's null: neither is an error. selectionLimit caps the batch
   where the OS supports it (iOS 14+, the Android photo picker); elsewhere the
   picker ignores it, so callers still slice to `limit` before uploading. */
export async function pickImages(limit: number): Promise<LocalImage[]> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) return [];

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.8,
    allowsMultipleSelection: true,
    selectionLimit: limit,
  });
  if (result.canceled || result.assets.length === 0) return [];
  return result.assets.slice(0, limit).map(toLocalImage);
}
