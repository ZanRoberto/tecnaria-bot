import React, { useState, useEffect, useRef } from 'react';
import './OracoloUI.css';

function OracoloUI() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchDocuments();
    // Auto-scroll to bottom on new response
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [response]);

  const fetchDocuments = async () => {
    try {
      const res = await fetch('/api/documents');
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (err) {
      console.error('Error fetching documents:', err);
    }
  };

  // Drag & drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload({ target: { files: e.dataTransfer.files } });
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (data.status === 'success') {
        setError(null);
        fetchDocuments();
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError(`Errore upload: ${err.message}`);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) {
      setError('Scrivi una domanda');
      return;
    }

    if (documents.length === 0) {
      setError('Carica almeno un documento');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) throw new Error('Errore nella richiesta');

      const data = await res.json();
      setResponse(data);
      setQuestion(''); // Clear input after submission
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (filename) => {
    if (!window.confirm(`Eliminare ${filename}?`)) return;

    try {
      const res = await fetch(`/api/documents/${filename}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchDocuments();
      }
    } catch (err) {
      setError(`Errore: ${err.message}`);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div className="oracolo-ui">
      {/* HEADER */}
      <header className="oracolo-header">
        <div className="header-content">
          <div className="logo-section">
            <div className="logo-icon">🏛️</div>
            <div className="logo-text">
              <h1>ORACOLO COVOLO</h1>
              <p>Il tuo assistente aziendale intelligente</p>
            </div>
          </div>
        </div>
        <div className="header-accent"></div>
      </header>

      {/* MAIN CONTAINER */}
      <div className="main-container">
        {/* SIDEBAR - DOCUMENTS */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <h2>📚 I Tuoi Documenti</h2>
            <span className="doc-count">{documents.length}</span>
          </div>

          {/* UPLOAD ZONE */}
          <div
            className={`upload-zone ${dragActive ? 'active' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              id="fileInput"
              onChange={handleFileUpload}
              disabled={uploadLoading}
              accept=".pdf,.xlsx,.xls,.docx,.doc,.txt"
              hidden
            />
            <label htmlFor="fileInput" className="upload-label">
              <div className="upload-icon">📤</div>
              <p className="upload-text">
                {uploadLoading ? '⏳ Caricamento...' : 'Trascina documenti qui'}
              </p>
              <p className="upload-hint">PDF, Excel, Word, TXT</p>
            </label>
          </div>

          {/* DOCUMENTS LIST */}
          <div className="documents-container">
            {documents.length === 0 ? (
              <div className="empty-state">
                <p>Nessun documento caricato</p>
              </div>
            ) : (
              documents.map((doc, idx) => (
                <div key={idx} className="document-card">
                  <div className="doc-icon">
                    {doc.filename.endsWith('.pdf') && '📄'}
                    {doc.filename.endsWith('.xlsx') && '📊'}
                    {doc.filename.endsWith('.docx') && '📝'}
                    {doc.filename.endsWith('.txt') && '📋'}
                  </div>
                  <div className="doc-info">
                    <p className="doc-name">{doc.filename}</p>
                    <p className="doc-meta">{(doc.file_size / 1024).toFixed(1)} KB</p>
                  </div>
                  <button
                    className="delete-doc"
                    onClick={() => handleDeleteDocument(doc.filename)}
                    title="Elimina"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        {/* MAIN CHAT AREA */}
        <main className="chat-main">
          {/* ERROR BANNER */}
          {error && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              <p>{error}</p>
              <button onClick={() => setError(null)} className="close-error">✕</button>
            </div>
          )}

          {/* CHAT MESSAGES */}
          <div className="chat-messages">
            {response ? (
              <>
                {/* USER QUESTION */}
                <div className="message user-message">
                  <div className="message-content">
                    <p>{response.meta?.question || question}</p>
                  </div>
                </div>

                {/* BOT RESPONSE */}
                <div className="message bot-message">
                  <div className="message-avatar">🏛️</div>
                  <div className="message-content">
                    <p className="response-text">{response.answer}</p>

                    {response.sources && response.sources.length > 0 && (
                      <div className="response-sources">
                        <p className="sources-label">Fonti:</p>
                        <div className="sources-list">
                          {response.sources.map((src, idx) => (
                            <span key={idx} className="source-badge">
                              {src}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <p className="message-time">
                      {new Date(response.timestamp).toLocaleTimeString('it-IT', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-chat">
                <div className="welcome-icon">🏛️</div>
                <h2>Benvenuto nell'Oracolo Covolo</h2>
                <p>Carica i tuoi documenti e fai una domanda</p>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* INPUT AREA */}
          <div className="input-area">
            <div className="input-wrapper">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Fai una domanda naturale... es: 'Quanto costa il miscelatore Gessi cromo?'"
                disabled={loading || documents.length === 0}
                rows="3"
                className="question-input"
              />
              <button
                onClick={handleAsk}
                disabled={loading || !question.trim() || documents.length === 0}
                className="ask-button"
              >
                <span className="button-icon">🔍</span>
                <span className="button-text">
                  {loading ? 'Elaborando...' : 'Chiedi'}
                </span>
              </button>
            </div>

            {documents.length === 0 && (
              <p className="input-hint">⚠️ Carica almeno un documento per iniziare</p>
            )}
          </div>
        </main>
      </div>

      {/* FOOTER */}
      <footer className="oracolo-footer">
        <p>🏢 Covolo SRL | Oracolo Intelligente | Powered by Claude</p>
      </footer>
    </div>
  );
}

export default OracoloUI;
