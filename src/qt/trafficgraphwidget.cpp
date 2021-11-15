// Copyright (c) 2011-2021 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <interfaces/node.h>
#include <qt/trafficgraphwidget.h>
#include <qt/clientmodel.h>

#include <QPainter>
#include <QPainterPath>
#include <QColor>
#include <QTimer>

#include <chrono>
#include <cmath>

#define DESIRED_SAMPLES         800

#define XMARGIN                 10
#define YMARGIN                 10

TrafficGraphWidget::TrafficGraphWidget(QWidget *parent) :
    QWidget(parent),
    timer(nullptr),
    fMax(0.0f),
    vSamplesIn(),
    vSamplesOut(),
    nLastBytesIn(0),
    nLastBytesOut(0),
    clientModel(nullptr)
{
    timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, &TrafficGraphWidget::updateRates);
}

void TrafficGraphWidget::setClientModel(ClientModel *model)
{
    clientModel = model;
    if(model) {
        nLastBytesIn = model->node().getTotalBytesRecv();
        nLastBytesOut = model->node().getTotalBytesSent();
    }
}

std::chrono::minutes TrafficGraphWidget::getGraphRange() const { return m_range; }

void TrafficGraphWidget::paintPath(QPainterPath &path, QQueue<float> &samples)
{
    int sampleCount = samples.size();
    if(sampleCount > 0 && fMax > 0) {
        int h = height() - YMARGIN * 2, w = width() - XMARGIN * 2;
        int x = XMARGIN + w;
        path.moveTo(x, YMARGIN + h);
        for(int i = 0; i < sampleCount; ++i) {
            x = XMARGIN + w - w * i / DESIRED_SAMPLES;
            int y = YMARGIN + h - (int)(h * 1.0 * (fToggle ? (pow(samples.at(i), 0.3) / pow(fMax, 0.3)) : (samples.at(i) / fMax)));
            path.lineTo(x, y);
        }
        path.lineTo(x, YMARGIN + h);
    }
}

void TrafficGraphWidget::mousePressEvent(QMouseEvent *event)
{
    QWidget::mousePressEvent(event);
    fToggle = !fToggle;
    timer->stop();
    timer->setInterval(timer->interval());
    timer->start();
}

void TrafficGraphWidget::paintEvent(QPaintEvent *)
{
    QPainter painter(this);
    painter.fillRect(rect(), Qt::black);

    if(fMax <= 0.0f) return;

    QColor axisCol(Qt::gray);
    int h = height() - YMARGIN * 2;
    painter.setPen(axisCol);
    painter.drawLine(XMARGIN, YMARGIN + h, width() - XMARGIN, YMARGIN + h);

    // decide what order of magnitude we are
    int base = floor(log10(fMax));
    float val = pow(10.0f, base);

    const QString units = tr("kB/s");
    const float yMarginText = 2.0;

    // if we drew 10 or 3 fewer lines, break them up at the next lower order of magnitude
    if(fMax / val <= (fToggle ? 10.0f : 3.0f)) {
        float oldval = val;
        val = pow(10.0f, base - 1);
        painter.setPen(axisCol.darker());
        painter.drawText(XMARGIN, YMARGIN + h - (h * 1.0 * (fToggle ? (pow(val, 0.3) / pow(fMax, 0.3)) : (val / fMax)))-yMarginText, QString("%1 %2").arg(val).arg(units));
        int count = 1;
        for(float y = val; y < (fToggle ? oldval : fMax); y += val, count++) {
            if(count % 10 == 0)
                continue;
            int yy = YMARGIN + h - (h * 1.0 * (fToggle ? (pow(y, 0.3) / pow(fMax, 0.3)) : (y / fMax)));
            painter.drawLine(XMARGIN, yy, width() - XMARGIN, yy);
        }
        val = oldval;
    }
    // draw lines
    painter.setPen(axisCol);
    for(float y = val; y < fMax; y += val) {
        int yy = YMARGIN + h - (h * 1.0 * (fToggle ? (pow(y, 0.3) / pow(fMax, 0.3)) : (y / fMax)));
        painter.drawLine(XMARGIN, yy, width() - XMARGIN, yy);
    }
    painter.drawText(XMARGIN, YMARGIN + h - (h * 1.0 * (fToggle ? (pow(val, 0.3) / pow(fMax, 0.3)) : (val / fMax)))-yMarginText, QString("%1 %2").arg(val).arg(units));

    painter.setRenderHint(QPainter::Antialiasing);
    if(!vSamplesIn.empty()) {
        QPainterPath p;
        paintPath(p, vSamplesIn);
        painter.fillPath(p, QColor(0, 255, 0, 128));
        painter.setPen(Qt::green);
        painter.drawPath(p);
    }
    if(!vSamplesOut.empty()) {
        QPainterPath p;
        paintPath(p, vSamplesOut);
        painter.fillPath(p, QColor(255, 0, 0, 128));
        painter.setPen(Qt::red);
        painter.drawPath(p);
    }
}

void TrafficGraphWidget::updateRates()
{
    if(!clientModel) return;

    quint64 bytesIn = clientModel->node().getTotalBytesRecv(),
            bytesOut = clientModel->node().getTotalBytesSent();
    float in_rate_kilobytes_per_sec = static_cast<float>(bytesIn - nLastBytesIn) / timer->interval();
    float out_rate_kilobytes_per_sec = static_cast<float>(bytesOut - nLastBytesOut) / timer->interval();
    vSamplesIn.push_front(in_rate_kilobytes_per_sec);
    vSamplesOut.push_front(out_rate_kilobytes_per_sec);
    nLastBytesIn = bytesIn;
    nLastBytesOut = bytesOut;

    while(vSamplesIn.size() > DESIRED_SAMPLES) {
        vSamplesIn.pop_back();
    }
    while(vSamplesOut.size() > DESIRED_SAMPLES) {
        vSamplesOut.pop_back();
    }

    float tmax = 0.0f;
    for (const float f : vSamplesIn) {
        if(f > tmax) tmax = f;
    }
    for (const float f : vSamplesOut) {
        if(f > tmax) tmax = f;
    }
    fMax = tmax;
    update();
}

void TrafficGraphWidget::setGraphRange(std::chrono::minutes new_range)
{
    m_range = new_range;
    const auto msecs_per_sample{std::chrono::duration_cast<std::chrono::milliseconds>(m_range) / DESIRED_SAMPLES};
    timer->stop();
    timer->setInterval(msecs_per_sample);

    clear();
}

void TrafficGraphWidget::clear()
{
    timer->stop();

    vSamplesOut.clear();
    vSamplesIn.clear();
    fMax = 0.0f;

    if(clientModel) {
        nLastBytesIn = clientModel->node().getTotalBytesRecv();
        nLastBytesOut = clientModel->node().getTotalBytesSent();
    }
    timer->start();
}
