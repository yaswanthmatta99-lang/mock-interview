// Bypass HTTPS requirement for localhost in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    if (typeof process !== 'undefined') {
        process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
    }
}

class VideoRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.stream = null;
        
        // DOM Elements
        this.videoPreview = document.getElementById('videoPreview');
        this.statusDiv = document.getElementById('status');
    }

    async startRecording() {
        try {
            // Request access to camera and microphone
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });
            
            // Display the camera feed
            this.videoPreview.srcObject = this.stream;
            this.videoPreview.muted = true; // Mute to avoid feedback
            await this.videoPreview.play();
            
            // Initialize MediaRecorder for video (we'll still record but not show it)
            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: 'video/webm;codecs=vp9,opus'
            });
            
            // Initialize speech recognition
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                throw new Error('Speech recognition not supported in this browser');
            }
            
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.transcript = '';
            
            this.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript + ' ';
                    } else {
                        interimTranscript += transcript;
                    }
                }
                
                document.getElementById('transcription').textContent = this.transcript + finalTranscript + interimTranscript;
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.showError('Error in speech recognition: ' + event.error);
            };
            
            // Start speech recognition
            this.recognition.start();
            
            // Reset recorded chunks
            this.recordedChunks = [];
            this.transcript = '';
            
            // Show transcription container
            document.getElementById('transcriptionContainer').style.display = 'block';
            document.getElementById('transcription').textContent = 'Listening...';
            
            // Start recording
            this.mediaRecorder.start(100);
            this.showStatus('Recording started... Speak now.', 'info');
            
        } catch (error) {
            console.error('Error accessing media devices:', error);
            this.showError('Could not access camera/microphone. Please check permissions.');
            throw error;
        }
    }

    async stopRecording() {
        return new Promise((resolve, reject) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
                resolve();
                return;
            }
            
            // Stop speech recognition if it's active
            if (this.recognition) {
                this.recognition.stop();
            }
            
            this.mediaRecorder.onstop = () => {
                // Finalize the transcription
                const transcription = document.getElementById('transcription');
                if (transcription.textContent === 'Listening...') {
                    transcription.textContent = 'No speech was detected. Please try again.';
                }
                
                // Stop all tracks in the stream
                if (this.stream) {
                    this.stream.getTracks().forEach(track => track.stop());
                }
                
                this.showStatus('Recording stopped', 'success');
                resolve();
            };
            
            // Stop recording
            this.mediaRecorder.stop();
        });
    }

    async uploadRecording(interviewId, questionId) {
        if (!interviewId || !questionId) {
            const error = new Error('Missing required parameters');
            console.error('Validation error:', { interviewId, questionId });
            this.showError('Invalid request. Please refresh the page and try again.');
            throw error;
        }

        if (this.recordedChunks.length === 0) {
            const error = new Error('No recording data available');
            console.error('Upload failed:', error);
            this.showError('No recording to upload. Please record your answer first.');
            throw error;
        }
        
        let uploadAbortController = new AbortController();
        const UPLOAD_TIMEOUT = 30000; // 30 seconds timeout
        
        try {
            this.showStatus('Preparing upload...', 'info');
            
            // Combine recorded chunks into a single blob
            const blob = new Blob(this.recordedChunks, { type: 'video/webm' });
            
            // Create form data
            const formData = new FormData();
            formData.append('video', blob, `answer_${Date.now()}_q${questionId}.webm`);
            formData.append('interview_id', interviewId);
            formData.append('question_id', questionId.toString());
            
            // Add metadata for debugging
            const metadata = {
                timestamp: new Date().toISOString(),
                userAgent: navigator.userAgent,
                blobSize: blob.size,
                questionId,
                interviewId
            };
            formData.append('metadata', JSON.stringify(metadata));
            
            console.debug('Starting upload:', metadata);
            
            // Set upload timeout
            const timeoutId = setTimeout(() => {
                uploadAbortController.abort();
                this.showError('Upload timed out. Please check your connection and try again.');
            }, UPLOAD_TIMEOUT);
            
            // Upload to server with progress tracking
            this.showStatus('Uploading your answer... (0%)', 'info');
            
            const response = await fetch('http://127.0.0.1:8009/upload_answer', {
                method: 'POST',
                body: formData,
                signal: uploadAbortController.signal,
                headers: {
                    'Accept': 'application/json',
                    'X-Request-ID': `upload-${Date.now()}`
                },
                mode: 'cors',
                credentials: 'include'
            }).catch(error => {
                if (error.name === 'AbortError') {
                    throw new Error('Upload was cancelled or timed out');
                }
                console.error('Network error:', error);
                throw new Error(`Network error: ${error.message}`);
            }).finally(() => clearTimeout(timeoutId));
            
            let responseData;
            try {
                responseData = await response.json();
            } catch (e) {
                console.error('Failed to parse JSON response:', e);
                throw new Error('Received invalid response from server');
            }
            
            if (!response.ok) {
                const errorMessage = responseData?.detail || 
                                   responseData?.message || 
                                   `Server error: ${response.status} ${response.statusText}`;
                
                console.error('Upload failed:', {
                    status: response.status,
                    statusText: response.statusText,
                    responseData,
                    headers: Object.fromEntries([...response.headers.entries()])
                });
                
                throw new Error(errorMessage);
            }
            
            console.debug('Upload successful:', responseData);
            this.showStatus('Answer uploaded successfully!', 'success');
            return responseData;
            
        } catch (error) {
            const errorDetails = {
                name: error.name,
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString(),
                interviewId,
                questionId,
                blobSize: this.recordedChunks.reduce((acc, chunk) => acc + chunk.size, 0)
            };
            
            if (error.response) {
                errorDetails.response = {
                    status: error.response.status,
                    statusText: error.response.statusText,
                    data: error.data
                };
            }
            
            console.error('Upload error:', errorDetails);
            
            // Show user-friendly error message
            let userMessage = 'Upload failed. ';
            if (error.message.includes('NetworkError')) {
                userMessage += 'Network error. Please check your internet connection.';
            } else if (error.message.includes('timed out')) {
                userMessage += 'The upload took too long. Please try again.';
            } else if (error.message.includes('cancelled')) {
                userMessage = 'Upload was cancelled.';
            } else {
                userMessage += error.message || 'Please try again later.';
            }
            
            this.showError(userMessage);
            throw error;
        } finally {
            // Clean up
            uploadAbortController = null;
        }
    }

    showStatus(message, type = 'info') {
        if (this.statusDiv) {
            this.statusDiv.textContent = message;
            this.statusDiv.className = `status ${type}`;
        }
    }

    showError(message) {
        this.showStatus(message, 'error');
    }
}