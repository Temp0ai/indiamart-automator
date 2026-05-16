package com.arihant.crm;

import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.net.http.SslError;
import android.webkit.SslErrorHandler;

public class ArihantWebViewClient extends WebViewClient {
    @Override
    public boolean shouldOverrideUrlLoading(WebView view, String url) {
        if (url.startsWith("https://wa.me/") || url.startsWith("https://api.whatsapp.com/")) {
            try {
                android.content.Intent intent = new android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url));
                view.getContext().startActivity(intent);
            } catch (Exception e) {
                view.loadUrl(url);
            }
            return true;
        }
        if (url.startsWith("tel:") || url.startsWith("mailto:")) {
            try {
                android.content.Intent intent = new android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url));
                view.getContext().startActivity(intent);
            } catch (Exception e) {}
            return true;
        }
        return false;
    }

    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        handler.proceed();
    }
}
