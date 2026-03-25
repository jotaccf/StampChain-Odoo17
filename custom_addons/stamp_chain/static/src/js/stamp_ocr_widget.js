/** @odoo-module **/
import { Component, useState, useRef } from "@odoo/owl";

const STAMP_REGEX = /^[A-Z]{5}\d{3}$/;
const TESSERACT_CDN =
    "https://cdnjs.cloudflare.com/ajax/libs"
    + "/tesseract.js/5.0.4/tesseract.min.js";

export class StampOcrWidget extends Component {
    static template = "stamp_chain.StampOcrWidget";
    static props = {
        onCodeConfirmed: { type: Function },
        label: { type: String, optional: true },
        confirmedCode: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            mode: "idle",
            rawCode: "",
            ocrConfidence: 0,
            errorMsg: "",
            videoReady: false,
        });
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");
        this.streamRef = null;
        this.tesseractLoaded = false;
    }

    async startCamera() {
        this.state.mode = "camera";
        this.state.errorMsg = "";
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "environment",
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            });
            this.streamRef = stream;
            const video = this.videoRef.el;
            video.srcObject = stream;
            await video.play();
            this.state.videoReady = true;
        } catch (err) {
            this.state.mode = "error";
            this.state.errorMsg =
                "Camara nao disponivel. Use a introducao manual.";
        }
    }

    async captureAndOcr() {
        this.state.mode = "processing";
        const video = this.videoRef.el;
        const canvas = this.canvasRef.el;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        const imageData = canvas.toDataURL("image/png");
        this.stopCamera();
        try {
            await this._loadTesseract();
            const result = await Tesseract.recognize(imageData, "eng", {
                tessedit_pageseg_mode: "8",
                tessedit_char_whitelist:
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            });
            const raw = (result.data.text || "")
                .trim()
                .toUpperCase()
                .replace(/\s+/g, "");
            const confidence = Math.round(result.data.confidence || 0);
            if (STAMP_REGEX.test(raw)) {
                this.state.rawCode = raw;
                this.state.ocrConfidence = confidence;
                this.state.mode = "confirm";
            } else {
                this.state.mode = "error";
                this.state.errorMsg =
                    'OCR leu: "' + raw + '" — formato invalido. Use manual.';
            }
        } catch (err) {
            this.state.mode = "error";
            this.state.errorMsg = "Erro OCR. Use introducao manual.";
        }
    }

    stopCamera() {
        if (this.streamRef) {
            this.streamRef.getTracks().forEach((t) => t.stop());
            this.streamRef = null;
        }
        this.state.videoReady = false;
    }

    async _loadTesseract() {
        if (this.tesseractLoaded) return;
        await new Promise((res, rej) => {
            const s = document.createElement("script");
            s.src = TESSERACT_CDN;
            s.onload = res;
            s.onerror = rej;
            document.head.appendChild(s);
        });
        this.tesseractLoaded = true;
    }

    confirmCode() {
        const code = this.state.rawCode;
        if (!STAMP_REGEX.test(code)) {
            this.state.errorMsg = "Codigo invalido. Formato: ZZAYC000";
            return;
        }
        this.state.mode = "idle";
        this.props.onCodeConfirmed(code);
    }

    rejectCode() {
        this.state.rawCode = "";
        this.state.mode = "manual";
    }

    useManual() {
        this.stopCamera();
        this.state.mode = "manual";
        this.state.errorMsg = "";
    }

    onManualInput(ev) {
        this.state.rawCode = ev.target.value.toUpperCase().trim();
    }

    submitManual() {
        const code = this.state.rawCode;
        if (!STAMP_REGEX.test(code)) {
            this.state.errorMsg =
                "Formato invalido. 5 letras + 3 digitos (ex: ZZAYC000)";
            return;
        }
        this.state.mode = "confirm";
        this.state.ocrConfidence = 100;
    }

    reset() {
        this.stopCamera();
        Object.assign(this.state, {
            mode: "idle",
            rawCode: "",
            ocrConfidence: 0,
            errorMsg: "",
            videoReady: false,
        });
    }
}
