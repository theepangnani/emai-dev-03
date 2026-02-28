import './UploadStatusIndicator.css';

interface UploadStatusIndicatorProps {
  status: 'uploading' | 'success' | 'error' | null;
}

export function UploadStatusIndicator({ status }: UploadStatusIndicatorProps) {
  if (!status || status === 'success') return null;

  if (status === 'uploading') {
    return (
      <div className="cm-upload-status">
        <span className="cm-upload-spinner" />
        Uploading &amp; extracting text...
      </div>
    );
  }

  return (
    <div className="cm-upload-status error">
      Upload failed
    </div>
  );
}
