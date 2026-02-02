import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide } from '../api/client';
import './StudyGuidePage.css';

export function StudyGuidePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGuide = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
      } catch (err) {
        setError('Failed to load study guide');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchGuide();
  }, [id]);

  const handleDelete = async () => {
    if (!guide || !confirm('Are you sure you want to delete this study guide?')) return;
    try {
      await studyApi.deleteGuide(guide.id);
      navigate('/dashboard');
    } catch (err) {
      setError('Failed to delete study guide');
    }
  };

  if (loading) {
    return (
      <div className="study-guide-page">
        <div className="loading">Loading study guide...</div>
      </div>
    );
  }

  if (error || !guide) {
    return (
      <div className="study-guide-page">
        <div className="error">{error || 'Study guide not found'}</div>
        <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="study-guide-page">
      <div className="study-guide-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
        <div className="header-actions">
          <button className="print-btn" onClick={() => window.print()}>Print</button>
          <button className="delete-btn" onClick={handleDelete}>Delete</button>
        </div>
      </div>

      <div className="study-guide-content">
        <h1>{guide.title}</h1>
        <p className="guide-meta">
          Created: {new Date(guide.created_at).toLocaleDateString()}
        </p>
        <div className="guide-body">
          {guide.content.split('\n').map((line, index) => {
            // Simple markdown-like rendering
            if (line.startsWith('# ')) {
              return <h1 key={index}>{line.substring(2)}</h1>;
            } else if (line.startsWith('## ')) {
              return <h2 key={index}>{line.substring(3)}</h2>;
            } else if (line.startsWith('### ')) {
              return <h3 key={index}>{line.substring(4)}</h3>;
            } else if (line.startsWith('**') && line.endsWith('**')) {
              return <p key={index}><strong>{line.slice(2, -2)}</strong></p>;
            } else if (line.startsWith('- ')) {
              return <li key={index}>{line.substring(2)}</li>;
            } else if (line.startsWith('* ')) {
              return <li key={index}>{line.substring(2)}</li>;
            } else if (line.match(/^\d+\. /)) {
              return <li key={index}>{line.replace(/^\d+\. /, '')}</li>;
            } else if (line.trim() === '') {
              return <br key={index} />;
            } else {
              return <p key={index}>{line}</p>;
            }
          })}
        </div>
      </div>
    </div>
  );
}
